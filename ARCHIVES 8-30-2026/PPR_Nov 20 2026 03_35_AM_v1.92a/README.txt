PPR 1.92a — EMBLEM FIX

This is a complete source build based on PPR 1.92.
The working Ko-fi tip control and existing relay behavior are retained.

Files in this release:
- PPR1.92a.py
- purple_python.jpg
- README.txt
- PPR1.92a_bundle.zip

Emblem handling:
- PPR first looks for prepared purple_python.png and purple_python.ico beside the script.
- If they are absent, PPR uses Windows PowerShell and .NET System.Drawing to create both from purple_python.jpg.
- The PNG is loaded directly by Tk 8.6; Pillow is not required.
- The ICO contains multiple standard sizes for Windows.
- Generated PNG and ICO files remain beside the script for later launches.
- Missing artwork or conversion failures now produce diagnostic log messages rather than failing silently.

Keep purple_python.jpg beside PPR1.92a.py.
