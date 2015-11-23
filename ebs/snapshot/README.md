EBS snapshot tool
=================

####Backup all your EBS volumes on Amazon Web Services (AWS)####

##How it works?##

1.Search all your EBS volumes.

2.Create a snapshot for each one with an expiration time (by default 30 days), this expiration time is only used for this script.

3.Delete all snapshot made by the script older than the expiration date.

##What do you need to use it?##

###Identify and Access Management (IAM) policy###
First you will need to create a new IAM policy and attach it to the user who will run the script (you can create a new user or use an existing one).

Create the new policy with the following attribute (you can find it in the **ebs-snapshot_aws-iam-policy.json** file):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "Stmt1447699344000",
      "Effect": "Allow",
      "Action": [
        "ec2:CreateSnapshot",
        "ec2:CreateTags",
        "ec2:DeleteSnapshot",
        "ec2:DescribeSnapshots",
        "ec2:DescribeTags",
        "ec2:DescribeVolumes"
      ],
      "Resource": [
        "*"
      ]
    }
  ]
}
```

###AWS Credentials###

####Configuration####

The AWS Python SDK, used in the script, need to be configured to use the right credentials. In order to do this you will create a profile.
By default the script call the profile name *ebs-snapshot* but you can create an other one and use it with the profile option `-p` of the script.

Create or modify the file **~/.aws/credentials** and add the credentials of the AWS user attached to the policy previously created (here is an example with a profile named *ebs-snapshot*):
```
[ebs-snapshot]
aws_access_key_id = YOUR_AWS_ACCESS_KEY_ID
aws_secret_access_key = YOUR_AWS_SECRET_ACCESS_KEY
region = YOUR_REGION
```
You can have multiple profile define in this file.

###Python and modules###

####Installation####

Install pip with:
```bash
sudo apt-get install python-pip -y
```
or
```bash
sudo yum install python-pip -y
```
according to your distribution.

Now you will have to install the AWS SDK package:
```bash
sudo pip install boto3
```

##How to use it?##

To run the script manually use:
```bash
./ebs-snapshot.py
```
This command will snapshot all your EBS volumes but can slow your instances while creating the differents snapshots.
The snapshots are incremental so it would be faster the next times.

You can also specify the volumes you want to snapshot with the option *--volumes* or *-v* and attribute them a specific expiration time value, in days (30 days by default), with the option *--expire-after* or *-e*.

For more help:
```bash
./ebs-snapshot --help
usage: ebs-snapshot.py [options]

optional arguments:
  -h, --help            show this help message and exit
  -v VOLUME_IDS [VOLUME_IDS ...], --volume-ids VOLUME_IDS [VOLUME_IDS ...]
                        Create and delete snapshot for the specified EBS
                        volumes
  -p PROFILE, --profile PROFILE
                        Use specific AWS profile (default 'ebs-snapshot')
  -e EXPIRE_AFTER, --expire-after EXPIRE_AFTER
                        Define a specific expiration time in days (default 30
                        days)
  -r REGION, --region REGION
                        Use specific AWS region (default 'us-east-1')
  -l, --list-volumes    List all EBS volumes
```

Setup an automatic job with the crontab. For example every day at 3AM:
```bash
00 03 * * * root /path_to_script/ebs-snapshot.py
```
Don't forget to put your **credentials** file to **/root/.aws/credentials**

##Logs##

All the logs are stored in '/var/log/ebs-snapshot.log', so make sure you have right permissions to access this file.
