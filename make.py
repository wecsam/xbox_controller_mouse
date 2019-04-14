#!/usr/bin/env python3
import common, config
import os, shutil, subprocess, version_update
MAJOR = 0
MINOR = 1
MAIN_FILENAME = "xbox_controller_mouse.py"

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
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
    # Make Python optimize code.
    os.putenv("PYTHONOPTIMIZE", "2")
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
    ).returncode == 0:
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
        ]).returncode == 0:
            # Reset the revision number.
            version_update.update(MAJOR, MINOR, build, 0)
            print("The process completed successfully.")
