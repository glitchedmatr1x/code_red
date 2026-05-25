# Clean Launch Retest: PlayRDR Launcher

Generated: 2026-05-23T22:55:10
Executable: `
D:\Games\Red Dead Redemption\PlayRDR.exe
`

## Launch Result
```text
start_error=
launcher_started=True
launcher_exit_code=0
rdr_processes_alive_after_45s=False
cleanup_action=stopped_any_remaining_RDR_or_PlayRDR_processes
```

## Processes Alive Before Cleanup
```text
(no RDR/PlayRDR processes alive at end of smoke window)
```

## Event Viewer Check
```text
TimeCreated  : 5/23/2026 10:54:48 PM
Id           : 1001
ProviderName : Windows Error Reporting
Message      : Fault bucket 2146941143962793735, type 5
               Event Name: BEX64
               Response: Not available
               Cab Id: 0
               
               Problem signature:
               P1: RDR.exe
               P2: 1.0.40.57107
               P3: 6711591d
               P4: CodeRED_Remote_Menu.asi
               P5: 0.0.0.0
               P6: 6a128d5e
               P7: 0000000000006051
               P8: c0000409
               P9: 0000000000000002
               P10: 
               
               Attached files:
               \\?\C:\ProgramData\Microsoft\Windows\WER\Temp\WER2C0E.tmp.dmp
               \\?\C:\ProgramData\Microsoft\Windows\WER\Temp\WER2D86.tmp.WERInternalMetadata.xml
               \\?\C:\ProgramData\Microsoft\Windows\WER\Temp\WER2DC6.tmp.xml
               \\?\C:\ProgramData\Microsoft\Windows\WER\Temp\WER2DD7.tmp.csv
               \\?\C:\ProgramData\Microsoft\Windows\WER\Temp\WER2DE8.tmp.txt
               
               These files may be available here:
               \\?\C:\ProgramData\Microsoft\Windows\WER\ReportArchive\AppCrash_RDR.exe_fd1349ab976d86d5fcf197a7305d2edb357b782b_80ebd3a5_53824530-3fba-4a78-89f8-62fd89f06045
               
               Analysis symbol: 
               Rechecking for solution: 0
               Report Id: ea07752d-0d21-4294-8331-689f2941d549
               Report Status: 268435456
               Hashed bucket: 81c8d9a24c5395b85dcb77986f92b707
               Cab Guid: 0

TimeCreated  : 5/23/2026 10:54:46 PM
Id           : 1000
ProviderName : Application Error
Message      : Faulting application name: RDR.exe, version: 1.0.40.57107, time stamp: 0x6711591d
               Faulting module name: CodeRED_Remote_Menu.asi, version: 0.0.0.0, time stamp: 0x6a128d5e
               Exception code: 0xc0000409
               Fault offset: 0x0000000000006051
               Faulting process id: 0x7904
               Faulting application start time: 0x01dceb41c532a99c
               Faulting application path: D:\Games\Red Dead Redemption\RDR.exe
               Faulting module path: D:\Games\Red Dead Redemption\CodeRED_Remote_Menu.asi
               Report Id: ea07752d-0d21-4294-8331-689f2941d549
               Faulting package full name: 
               Faulting package-relative application ID: 

TimeCreated  : 5/23/2026 10:54:26 PM
Id           : 1001
ProviderName : Windows Error Reporting
Message      : Fault bucket 1554811370419903786, type 5
               Event Name: BEX64
               Response: Not available
               Cab Id: 0
               
               Problem signature:
               P1: RDR.exe
               P2: 1.0.40.57107
               P3: 6711591d
               P4: ucrtbase.dll
               P5: 10.0.19041.3636
               P6: 81cf5d89
               P7: 000000000007286e
               P8: c0000409
               P9: 0000000000000007
               P10: 
               
               Attached files:
               \\?\C:\ProgramData\Microsoft\Windows\WER\Temp\WERD7D4.tmp.dmp
               \\?\C:\ProgramData\Microsoft\Windows\WER\Temp\WERD823.tmp.WERInternalMetadata.xml
               \\?\C:\ProgramData\Microsoft\Windows\WER\Temp\WERD872.tmp.xml
               \\?\C:\ProgramData\Microsoft\Windows\WER\Temp\WERD872.tmp.csv
               \\?\C:\ProgramData\Microsoft\Windows\WER\Temp\WERD892.tmp.txt
               
               These files may be available here:
               \\?\C:\ProgramData\Microsoft\Windows\WER\ReportArchive\AppCrash_RDR.exe_4979d4b1afb6fad9176e96efc454fa6429c8187_80ebd3a5_2524b938-9c45-4f42-b9c8-c04a490d504f
               
               Analysis symbol: 
               Rechecking for solution: 0
               Report Id: cdf15848-1abc-4ffe-b879-3f248d140218
               Report Status: 268435456
               Hashed bucket: 43786082119e14d18593ccb4229ddd2a
               Cab Guid: 0

TimeCreated  : 5/23/2026 10:54:25 PM
Id           : 1000
ProviderName : Application Error
Message      : Faulting application name: RDR.exe, version: 1.0.40.57107, time stamp: 0x6711591d
               Faulting module name: ucrtbase.dll, version: 10.0.19041.3636, time stamp: 0x81cf5d89
               Exception code: 0xc0000409
               Fault offset: 0x000000000007286e
               Faulting process id: 0x68d0
               Faulting application start time: 0x01dceb41c691328e
               Faulting application path: D:\Games\Red Dead Redemption\RDR.exe
               Faulting module path: C:\WINDOWS\System32\ucrtbase.dll
               Report Id: cdf15848-1abc-4ffe-b879-3f248d140218
               Faulting package full name: 
               Faulting package-relative application ID:
```
