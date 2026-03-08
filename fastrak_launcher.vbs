' InvisibleLauncher.vbs - Launches Python script invisibly
' Define path to your Python script
strPythonScript = "P:\_Script\floriandheer\fastrak_hub.py"

' Create a shell object
Set objShell = CreateObject("WScript.Shell")

' Run the Python script invisibly using pythonw.exe to ensure no terminal window
' The 0 parameter makes it completely hidden
' The False parameter makes it not wait for completion
objShell.Run "pythonw.exe """ & strPythonScript & """", 0, False

' Clean up
Set objShell = Nothing