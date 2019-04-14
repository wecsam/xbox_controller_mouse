# Xbox Controller as Mouse

This script allows you to use an Xbox controller as a pointing device with a
Windows PC. The button mappings are printed when the script starts.

## Running from source

To run the script from the source code, first clone the
[Xbox-360-Controller-for-Python](https://github.com/wecsam/Xbox-360-Controller-for-Python)
repository locally. Follow the instructions in its README to set it up. Then,
create a file called `config.py` in the root of this repository and add the
following line:

    XINPUT_DIR = r"C:\path\to\Xbox-360-Controller-for-Python"

Replace `r"C:\path\to\Xbox-360-Controller-for-Python"` with a string of the
path to where you cloned **Xbox-360-Controller-for-Python**.

Next, run this command to install dependencies:

    pip install -r requirements.txt

Run this command to run the script:

	xbox_controller_mouse.py

Optionally, run this command to compile a new binary:

	make.py

If your system isn't set up to run Python files with the Python interpreter,
then prepend `python` or a path to the interpreter to both commands.
