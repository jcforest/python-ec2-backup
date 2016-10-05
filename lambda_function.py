
import ec2_backup


def handler(event, content):
    ec2_backup.backup()
