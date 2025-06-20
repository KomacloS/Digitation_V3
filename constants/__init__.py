
import os

# Path to the functions reference table bundled in this package
# ``constants/functions_ref.txt`` lives beside ``__init__.py`` so this
# relative join works both from source and when frozen with PyInstaller.
FUNCTIONS_REF_PATH = os.path.join(os.path.dirname(__file__), "functions_ref.txt")
