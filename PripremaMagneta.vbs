'' Pokrece Kosnicu Print bez ijednog prozora konzole.
' Server sam otvara prozor aplikacije (Edge --app) i ikonicu pored sata.
' Ako nesto ne radi, pokreni pokreni.bat da vidis poruke.

Option Explicit

Dim fso, ljuska, mapa, pyw, py
Set fso = CreateObject("Scripting.FileSystemObject")
Set ljuska = CreateObject("WScript.Shell")

mapa = fso.GetParentFolderName(WScript.ScriptFullName)
pyw  = mapa & "\.venv\Scripts\pythonw.exe"
py   = mapa & "\.venv\Scripts\python.exe"

ljuska.CurrentDirectory = mapa

' --- precica na Desktopu: uvek pokazuje na ovaj folder ---
Dim precica, ikona
Set precica = ljuska.CreateShortcut(ljuska.SpecialFolders("Desktop") & "\Ko" & ChrW(353) & "nica Print.lnk")
ikona = mapa & "\kosnica.ico"
On Error Resume Next
precica.TargetPath = WScript.ScriptFullName
precica.WorkingDirectory = mapa
precica.Description = "Ko" & ChrW(353) & "nica Print"
If fso.FileExists(ikona) Then precica.IconLocation = ikona & ", 0"
precica.Save
' stara precica iz vremena kad se app zvala Priprema magneta (P1)
If fso.FileExists(ljuska.SpecialFolders("Desktop") & "\Priprema magneta.lnk") Then fso.DeleteFile ljuska.SpecialFolders("Desktop") & "\Priprema magneta.lnk", True
Err.Clear
On Error GoTo 0

If fso.FileExists(pyw) Then
    ljuska.Run """" & pyw & """ """ & mapa & "\server.py""", 0, False
ElseIf fso.FileExists(py) Then
    ljuska.Run """" & py & """ """ & mapa & "\server.py""", 0, False
Else
    ' Prvo pokretanje u ovom folderu: okruzenje jos ne postoji, bat ga pravi.
    ljuska.Run """" & mapa & "\pokreni.bat""", 1, False
End If
