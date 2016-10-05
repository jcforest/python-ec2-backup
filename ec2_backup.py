#!/usr/bin/python
# EC2Backup
# Author: Dennis Kroon
# Version: 1.0

import boto3
import datetime
import time
from time import mktime
import ec2_backup_config #configuration file in same directory
import logging

logger = logging.getLogger('EC2Backup')
hdlr = logging.FileHandler(ec2_backup_config.logfile)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.INFO)

tagNameFrequency = 'EC2BackupFrequency'
tagNameRetain = 'EC2BackupRetain'
tagNameRemove = 'EC2BackupRemove'


def tagValueByKey(objs, key):
    tag_value = [tag['Value'] for tag in objs if tag['Key'] == key]

    if len(tag_value) == 0:
        return None
    else:
        return tag_value[0]



def ami_backup():
    print 'Backup started\n'
    # read server info from config file
    servers = ec2_backup_config.servers
    aws_config = ec2_backup_config.aws
    default_backup_retention = ec2_backup_config.default_backup_retention


    for server in servers :
        server_name = server['name']
        account_profile = server['profile']
        server_region = server['region']

        # create ec2 connection using boto config profiles
        # ec2 = boto.ec2.connect_to_region(server_region, profile_name = account_profile)
        session = boto3.Session(aws_access_key_id=aws_config['access_key_id'], aws_secret_access_key=aws_config['secret_access_key'], region_name=server_region)
        boto3_ec2 = session.resource('ec2', server_region)

        if ( boto3_ec2 is None  ):
            print 'ERROR - ' + server_name + ': unable to connect(boto3)'
            logger.error( server_name + ': unable to connect to region ' + server_region + ' with profile ' + account_profile )
            continue

        instances = boto3_ec2.instances.filter(
            Filters=[{'Name': 'instance-state-name', 'Values': ['*']}, {'Name': 'tag:' + tagNameFrequency, 'Values': ['*']}])
        for instance in instances:

            instance_name = tagValueByKey(instance.tags,'Name')
            instance_bk_frequency = tagValueByKey(instance.tags, tagNameFrequency)
            instance_bk_retain = tagValueByKey(instance.tags, tagNameRetain)

            if instance_name == None:
                instance_name = instance.id
            if instance_bk_retain == None:
                instance_bk_retain = str(default_backup_retention)

            print '\n' + server_name + ': ' + instance_name + ' - frequency: ' + instance_bk_frequency + ', retain: ' + instance_bk_retain

            current_datetime = datetime.datetime.now()
            date_stamp = current_datetime.strftime('%Y-%m-%d_%H-%M-%S')
            ami_name = instance_name + '_' + instance_bk_frequency + '_' + date_stamp
            ami_remove = (current_datetime + datetime.timedelta(days=int(instance_bk_retain))).strftime('%Y-%m-%d')

            try:
                image = instance.create_image(Name=ami_name, Description='Created by EC2Backup', NoReboot=True, DryRun=False)
            except Exception, e:
                logger.error('Backup ' + server_name + ': ' + e.message)
                print 'Error - ' + server_name + ': ' + e.message
                continue
            logger.info('Backup ' + server_name + ': ' + ami_name)
            print 'AMI creation started'
            print 'AMI name: ' + ami_name
            image.create_tags(DryRun=False, Tags=[{'Key': 'Name','Value': ami_name}])
            image.create_tags(DryRun=False, Tags=[{'Key': str(tagNameRemove), 'Value': str(ami_remove)}])

        # deregister old images
        print 'Deletion of old AMIs'
        images = boto3_ec2.images.filter(Filters=[{'Name': 'tag-key', 'Values': [tagNameRemove]}])
        for image in images:
            image_name = tagValueByKey(image.tags, 'Name')
            image_remove_date = mktime(time.strptime(tagValueByKey(image.tags, tagNameRemove), '%Y-%m-%d'))
            current_timestamp = mktime(current_datetime.timetuple())
            diff_minutes = (current_timestamp - image_remove_date) / 60
            if (diff_minutes > 0):
                image.deregister(DryRun=False)
                print image_name + ' deleted'
                logger.info('Deleted AMI ' + image_name)
            else:
                print image_name + ' kept'
                logger.info('Kept AMI ' + image_name)
    # end servers loop
    print '\nBackup completed'

ami_backup()
