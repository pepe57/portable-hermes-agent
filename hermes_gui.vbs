Set WshShell = CreateObject("WScript.Shell")
Set FileSystem = CreateObject("Scripting.FileSystemObject")
AppDir = FileSystem.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = AppDir
WshShell.Run """" & AppDir & "\hermes_gui.bat""", 0, False
