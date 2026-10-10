"""Data for synthetic restoration fixtures, mapped to MITRE ATT&CK persistence/impact techniques.

Nothing here executes an attack or touches a real system. ATT&CK supplies the taxonomy only;
the observations, artifacts and expected answers are author-created.

malicious artifact: (id, type, description, remediation kind)
benign artifact:    (id, type, description)
file:               (id, status, latest_backup_clean)
"""

SPECS = {
    'T1053.005': dict(
        malicious=[('task-updatersvc', 'scheduled_task', "Scheduled task 'UpdaterSvc' runs a PowerShell payload at logon.", 'remove_artifact')],
        benign=[('task-wuc', 'scheduled_task', "Scheduled task 'WindowsUpdateCheck' created by approved change CHG-1042.")],
        files=[],
        observation="EDR confirms scheduled task task-updatersvc is attacker persistence on workstation-01."),
    'T1547.001': dict(
        malicious=[('runkey-onedrivesync', 'registry_run_key', "Run key 'OneDriveSync' launches an unsigned binary from a temp folder.", 'remove_artifact')],
        benign=[('runkey-teams', 'registry_run_key', "Run key 'Teams' installed by the managed software deployment.")],
        files=[],
        observation="EDR confirms registry Run key runkey-onedrivesync is attacker persistence on workstation-01."),
    'T1543.003': dict(
        malicious=[('svc-winupdhelper', 'windows_service', "Service 'WinUpdHelper' runs a binary that beacons to c2-01.", 'remove_artifact')],
        benign=[('svc-backupagent', 'windows_service', "Service 'BackupAgent' belongs to the approved backup product.")],
        files=[],
        observation="EDR confirms Windows service svc-winupdhelper is attacker persistence on workstation-01."),
    'T1136.001': dict(
        malicious=[('acct-svcbackup2', 'local_account', "Local administrator account 'svc_backup2' created by the attacker.", 'disable_account')],
        benign=[('acct-svcbackup', 'local_account', "Local administrator account 'svc_backup' used by the approved backup job.")],
        files=[],
        observation="Identity telemetry confirms local account acct-svcbackup2 was created by the attacker on workstation-01."),
    'T1505.003': dict(
        malicious=[('file-shell-aspx', 'web_file', "File 'uploads/shell.aspx' is a web shell executing attacker commands.", 'remove_artifact')],
        benign=[('file-health-aspx', 'web_file', "File 'health.aspx' is the approved load balancer health check.")],
        files=[],
        observation="EDR confirms web file file-shell-aspx is an attacker web shell on web-01."),
    'T1490': dict(
        malicious=[('svc-vss', 'disabled_service', "Volume Shadow Copy service was disabled by the attacker to block recovery.", 'reenable_service')],
        benign=[('svc-spooler', 'disabled_service', "Print Spooler is disabled under approved hardening change CHG-0977.")],
        files=[],
        observation="EDR confirms the attacker disabled svc-vss on workstation-01 to inhibit recovery."),
    'T1486': dict(
        malicious=[('bin-ransom', 'binary', "Binary 'locker.exe' encrypted user files on workstation-01.", 'remove_artifact')],
        benign=[('bin-backupcli', 'binary', "Binary 'backupcli.exe' is the approved backup client.")],
        files=[('file-finance', 'encrypted', True), ('file-hr', 'encrypted', True), ('file-payroll', 'encrypted', False)],
        observation=("EDR confirms bin-ransom encrypted file-finance, file-hr and file-payroll on workstation-01. "
                     "Backups for file-finance and file-hr predate the intrusion; the only backup of file-payroll was taken after encryption began.")),
}

AUTHORIZED_NOTE = ("Verified authorized exercise with approved change record and asset owner confirmation; "
                   "no unauthorized activity. The technique label alone is not evidence of an attack.")
