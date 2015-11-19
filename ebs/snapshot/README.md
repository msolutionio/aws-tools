EBS snapshot tool
=================

####Backup all your EBS volumes on Amazon Web Services (AWS)####

##How it works?##

1.Search all your EBS volumes

2.Create a snapshot for each one

3.Delete all snapshot made by the script older than 30 days

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

###AWS Command Line Interface (CLI)###

####Installation####

Refer to [the official AWS documentation](http://docs.aws.amazon.com/cli/latest/userguide/installing.html) for the installation.

####Configuration####

The AWS CLI need to be configured to use the right credentials. In order to do this you will create a profile for the AWS CLI.
By default the script call the profile name *ebs-snapshot* but you can create an other one and use it with the profile option `-p` of the script.

You can use the command **aws configure** to set a default profile for the AWS CLI tool

Create or modify the file **~/.aws/config** and add the credentials of the AWS user attached to the policy previously created (here is an example with a profile named *ebs-snapshot*):
```
[profile ebs-snapshot]
aws_access_key_id = YOUR_AWS_ACCESS_KEY_ID
aws_secret_access_key = YOUR_AWS_SECRET_ACCESS_KEY
region = YOUR_REGION
```

##How to use it?##

Just run the script with:
```bash
sudo ./ebs-snapshot
```

Use the option `-p` to use a different profile than *ebs-snapshot*

Use the option `-r` to set a different region

Use the option `-v` to snapshot only the provided volumes
