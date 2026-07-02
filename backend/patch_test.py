with open("test_cv2_import.spec", "r") as f:
    lines = f.readlines()
with open("test_cv2_import.spec", "w") as f:
    for line in lines:
        if "from PyInstaller.utils.hooks import collect_all" not in line and line.startswith("a = Analysis"):
            f.write("from PyInstaller.utils.hooks import collect_all\n")
            f.write("datas, binaries, hiddenimports = collect_all('numpy')\n")
            f.write("a = Analysis(\n")
        elif "datas=[]" in line:
            f.write("    datas=datas,\n")
        elif "binaries=[]" in line:
            f.write("    binaries=binaries,\n")
        elif "hiddenimports=[]" in line:
            f.write("    hiddenimports=hiddenimports,\n")
        else:
            f.write(line)
