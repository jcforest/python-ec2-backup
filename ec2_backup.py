#!/usr/bin/python
# EC2Backup
# Author: Dennis Kroon
# Version: 1.0

import boto.ec2
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


def ami_backup():
    print "Backup started\n"
    # read server info from config file
    servers = ec2_backup_config.servers
    default_backup_retention = ec2_backup_config.default_backup_retention


    for server in servers :
        server_name = server['name']
        account_profile = server['profile']
        server_tag = server['tag']
        server_region = server['region']

        # create ec2 connection using boto config profiles
        ec2 = boto.ec2.connect_to_region(server_region, profile_name = account_profile)
        if ( ec2 is None  ):
            print "ERROR - " + server_name + ": unable to connect"
            logger.error( server_name + ": unable to connect to region " + server_region + " with profile " + account_profile )
            continue

        # get instances with tag Name 'EC2BackupFrequency'
        reservations = ec2.get_all_reservations(filters = {'tag:' + tagNameFrequency: '*', 'instance-state-name':'*'})

        if ( len(reservations) == 0 ):
            print "ERROR - " + server_name + ": unable to find server with tag name  " + server_tag
            logger.error( server_name + ": unable to find server with tag name " + server_tag )
            continue
        # loop through reservations and instances
        for reservation in reservations:
            for instance in reservation.instances:
                #print instance.__dict__.keys()
                if 'Name' in instance.tags:
                    instance_name = instance.tags['Name']
                else:
                    instance_name = instance.id

                instance_bk_frequency = instance.tags[tagNameFrequency]
                if tagNameRetain in instance.tags:
                    instance_bk_retain = instance.tags[tagNameRetain]
                else:
                    instance_bk_retain = str(default_backup_retention)

                print "\n" + server_name + ": " + instance_name + " - frequency: " + instance_bk_frequency + ", retain: " + instance_bk_retain

                current_datetime = datetime.datetime.now()
                date_stamp = current_datetime.strftime("%Y-%m-%d_%H-%M-%S")
                ami_name = instance_name + "_" + instance_bk_frequency + "_" + date_stamp
                ami_remove = (current_datetime + datetime.timedelta(days=int(instance_bk_retain))).strftime("%Y-%m-%d")

                try:
                    ec2_id = instance.create_image(ami_name, description='Created by EC2Backup', no_reboot=True, dry_run=False)
                except Exception, e:
                    logger.error("Backup " + server_name + ": " + e.message)
                    continue
                logger.info("Backup " + server_name + ": " + ami_name)
                print "AMI creation started"
                print "AMI name: " + ami_name
                images = ec2.get_all_images(image_ids = ec2_id)
                image = images[0]
                image.add_tag("Name", ami_name)
                image.add_tag(tagNameRemove, ami_remove)

        # deregister old images
        print "Deletion of old AMIs"
        images = ec2.get_all_images(filters={'tag:' + tagNameRemove: '*'})
        for image in images:
            image_name = image.tags['Name']
            image_remove_date = mktime(time.strptime(image.tags[tagNameRemove], "%Y-%m-%d"))
            current_timestamp = mktime(current_datetime.timetuple())
            diff_minutes = (current_timestamp - image_remove_date) / 60
            if (diff_minutes > 0):
                image.deregister(delete_snapshot=True, dry_run=False)
                print image_name + " deleted"
                logger.info("Deleted AMI " + image_name)
            else:
                print image_name + " kept"
                logger.info("Kept AMI " + image_name)
    # end servers loop
    print "\nBackup completed"

ami_backup()
