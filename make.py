#!/usr/bin/env python3
import common, config, version_update
import git, itertools, os, shutil, subprocess, sys
MAJOR = 0
MINOR = 1
MAIN_FILENAME = "xbox_controller_mouse.py"
BUILD_FILES = ("make.py", "version.py")

def uncommitted_changes_non_make(repo):
    # Check for changes that have been staged for commit (but not committed).
    # Check for changes that have not been staged for commit.
    for diff in itertools.chain(
        repo.index.diff(repo.head.commit),
        repo.index.diff(None)
    ):
        if diff.b_path not in BUILD_FILES:
            print("Uncommitted changes in file:", diff.b_path)
            return True
    # Check for untracked files.
    for path in repo.untracked_files:
        if path not in BUILD_FILES:
            print("Untracked file:", path)
            return True
    # Except for changes to this file, there are no uncommitted changes.
    return False
def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    repo = git.Repo(os.curdir)
    # Make sure that all changes except for those in files that are related to
    # the make process are committed in git. This is important because a new
    # commit will be added and tagged at the end.
    if uncommitted_changes_non_make(repo):
        print("There are uncommitted changes to files not related to making.")
        return 1
    # Update the version number.
    version = version_update.version_module()
    if (MAJOR, MINOR) == (version.MAJOR, version.MINOR):
        # Increment the build number.
        build = version.BUILD + 1
        # Don't change the revision number until after building.
        revision = version.REVISION
    else:
        # The major or minor version has changed. Reset the build number.
        build = 0
        # Also, reset the revision number.
        revision = 0
    version_update.update(MAJOR, MINOR, build, revision)
    print(
        "Building {} {}.{}.{}.{}...".format(
            common.PRODUCT_NAME,
            MAJOR,
            MINOR,
            build,
            revision
        )
    )
    # Build.
    script_name = os.path.splitext(MAIN_FILENAME)[0]
    distpath = os.path.join(os.curdir, common.PRODUCT_NAME)
    bin_path = os.path.join(distpath, common.PRODUCT_NAME)
    if subprocess.run(
        (
            "pyinstaller",
            "--noconfirm",
            "--onefile", MAIN_FILENAME,
            "--distpath", bin_path,
            "--paths", config.XINPUT_DIR
        )
    ).returncode != 0:
        print("PyInstaller failed.")
        return 2
    # Create a ZIP file.
    print("Creating ZIP file...")
    if subprocess.run([
        "powershell",
        "Compress-Archive",
        '"' + bin_path + '\\"',
        '"' + os.path.join(
            distpath,
            "{}_{}.{}.{}.{}.zip".format(
                script_name,
                MAJOR,
                MINOR,
                build,
                revision
            )
        ) + '"'
    ]).returncode != 0:
        print("ZIP file creation failed.")
        return 3
    # Create a commit and tag it.
    # TODO: repo.index.add seems to mess up line endings
    # repo.index.add(BUILD_FILES, write=True)
    subprocess.run(("git", "add") + BUILD_FILES)
    repo.index.commit(
        "Built version {}.{}.{}.{}".format(
            MAJOR,
            MINOR,
            build,
            revision
        )
    )
    tag = "v{}.{}.{}.{}".format(
        MAJOR,
        MINOR,
        build,
        revision
    )
    repo.create_tag(tag)
    # Reset the revision number.
    version_update.update(MAJOR, MINOR, build, 0)
    print("The process completed successfully.")
    print("You can share the tag by running: git push origin", tag)
    return 0

if __name__ == "__main__":
    sys.exit(main())
