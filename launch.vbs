Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
folder = fs.GetParentFolderName(WScript.ScriptFullName)
portable = folder & "\QuickTranslator.exe"
If fs.FileExists(portable) Then
    shell.Run Chr(34) & portable & Chr(34), 0, False
Else
    launcher = shell.ExpandEnvironmentStrings("%LocalAppData%\Programs\Python\Launcher\pyw.exe")
    shell.Run Chr(34) & launcher & Chr(34) & " " & Chr(34) & folder & "\translator.pyw" & Chr(34), 0, False
End If
