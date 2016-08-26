

# COMMON
#_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/
DEFAULT_CURRENCY = "USD"

SERVICE_CODE_AWS_DATA_TRANSFER = 'AWSDataTransfer'

REGION_MAP = {'us-east-1':'US East (N. Virginia)',
              'us-west-1':'US West (N. California)',
              'us-west-2':'US West (Oregon)',
              'eu-west-1':'EU (Ireland)',
              'eu-central-1':'EU (Frankfurt)',              
              'ap-northeast-1':'Asia Pacific (Tokyo)',
              'ap-northeast-2':'Asia Pacific (Seoul)',              
              'ap-southeast-1':'Asia Pacific (Singapore)',
              'ap-southeast-2':'Asia Pacific (Sydney)',              
              'sa-east-1':'South America (Sao Paulo)',
              'ap-south-1':'Asia Pacific (Mumbai)'
              }

SERVICE_EC2 = 'ec2'
SERVICE_ELB = 'elb'
SERVICE_EBS = 'ebs'
SERVICE_S3 = 's3'

SUPPORTED_SERVICES = (SERVICE_S3, SERVICE_EC2)

SUPPORTED_REGIONS = ('us-east-1', 'us-west-1', 'us-west-2', 'eu-west-1', 'eu-central-1',
                     'ap-northeast-1', 'ap-northeast-2', 'ap-southeast-1', 'ap-southeast-2',
                     'sa-east-1','ap-south-1')

SUPPORTED_INSTANCE_TYPES = ('t1.micro' , 't2.nano' , 't2.micro' , 't2.small' , 't2.medium' , 't2.large' , 'm1.small' ,
                            'm1.medium' , 'm1.large' , 'm1.xlarge' , 'm3.medium' , 'm3.large' , 'm3.xlarge' , 'm3.2xlarge' ,
                            'm4.large' , 'm4.xlarge' , 'm4.2xlarge' , 'm4.4xlarge' , 'm4.10xlarge' , 'm2.xlarge' ,
                            'm2.2xlarge' , 'm2.4xlarge' , 'cr1.8xlarge' , 'r3.large' , 'r3.xlarge' , 'r3.2xlarge' ,
                            'r3.4xlarge' , 'r3.8xlarge' , 'x1.4xlarge' , 'x1.8xlarge' , 'x1.16xlarge' , 'x1.32xlarge',
                            'i2.xlarge' , 'i2.2xlarge' , 'i2.4xlarge' , 'i2.8xlarge' , 'hi1.4xlarge' , 'hs1.8xlarge' ,
                            'c1.medium' , 'c1.xlarge' , 'c3.large' , 'c3.xlarge' , 'c3.2xlarge' , 'c3.4xlarge' ,
                            'c3.8xlarge' , 'c4.large' , 'c4.xlarge' , 'c4.2xlarge' , 'c4.4xlarge' , 'c4.8xlarge' ,
                            'cc1.4xlarge' , 'cc2.8xlarge' , 'g2.2xlarge' , 'g2.8xlarge' , 'cg1.4xlarge' , 'd2.xlarge',
                            'd2.2xlarge' , 'd2.4xlarge' , 'd2.8xlarge')


SERVICE_INDEX_MAP = {'s3':'AmazonS3','ec2':'AmazonEC2'}


PRODUCT_FAMILY_COMPUTE_INSTANCE = 'Compute Instance'
PRODUCT_FAMILY_DATA_TRANSFER = 'Data Transfer'
PRODUCT_FAMILY_FEE = 'Fee'
PRODUCT_FAMILY_API_REQUEST = 'API Request'
PRODUCT_FAMILY_STORAGE = 'Storage'
PRODUCT_FAMILY_SYSTEM_OPERATION = 'System Operation'
PRODUCT_FAMILY_LOAD_BALANCER = 'Load Balancer'
PRODUCT_FAMILY_SNAPSHOT = "Storage Snapshot"


INFINITY = 'Inf'

SORT_CRITERIA_REGION = 'region'
SORT_CRITERIA_S3_STORAGE_CLASS = 'storage-class'



#_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/
#EC2
EC2_OPERATING_SYSTEM_LINUX = 'Linux'
EC2_OPERATING_SYSTEM_BYOL = 'Windows BYOL'
EC2_OPERATING_SYSTEM_WINDOWS = 'Windows'
EC2_OPERATING_SYSTEM_SUSE = 'Suse'
EC2_OPERATING_SYSTEM_SQL_WEB = 'SQL Web'
EC2_OPERATING_SYSTEM_RHEL = 'RHEL'

STORAGE_MEDIA_SSD = "SSD-backed"
STORAGE_MEDIA_HDD = "HDD-backed"
STORAGE_MEDIA_S3 = "AmazonS3"

EBS_VOLUME_TYPE_PIOPS = "Provisioned IOPS"
EBS_VOLUME_TYPE_MAGNETIC = "Magnetic"
EBS_VOLUME_TYPE_GENERAL_PURPOSE = "General Purpose"

#Values that are valid in the calling script (which could be a Lambda function or any Python module)
#To make things simpler, these are the values that are used in the AWS API
#OS
SCRIPT_OPERATING_SYSTEM_LINUX = 'linux'
SCRIPT_OPERATING_SYSTEM_WINDOWS_BYOL = 'windowsbyol'
SCRIPT_OPERATING_SYSTEM_WINDOWS = 'windows'
SCRIPT_OPERATING_SYSTEM_SUSE = 'suse'
SCRIPT_OPERATING_SYSTEM_SQL_WEB = 'sqlweb'
SCRIPT_OPERATING_SYSTEM_RHEL = 'rhel'

#EBS
SCRIPT_EBS_VOLUME_TYPE_STANDARD = 'standard'
SCRIPT_EBS_VOLUME_TYPE_IO1 = 'io1'
SCRIPT_EBS_VOLUME_TYPE_GP2 = 'gp2'
SCRIPT_EBS_VOLUME_TYPE_SC1 = 'sc1'
SCRIPT_EBS_VOLUME_TYPE_ST1 = 'st1'



SUPPORTED_EC2_OPERATING_SYSTEMS = (SCRIPT_OPERATING_SYSTEM_LINUX, 
                                   SCRIPT_OPERATING_SYSTEM_WINDOWS_BYOL,
                                   SCRIPT_OPERATING_SYSTEM_SUSE,
                                   SCRIPT_OPERATING_SYSTEM_SQL_WEB,
                                   SCRIPT_OPERATING_SYSTEM_RHEL)

EC2_OPERATING_SYSTEMS_MAP = {SCRIPT_OPERATING_SYSTEM_LINUX:'Linux', 
                             SCRIPT_OPERATING_SYSTEM_WINDOWS_BYOL:'Windows BYOL',
                             SCRIPT_OPERATING_SYSTEM_WINDOWS:'Windows',
                             SCRIPT_OPERATING_SYSTEM_SUSE:'SUSE',
                             SCRIPT_OPERATING_SYSTEM_SQL_WEB:'SQL Web',
                             SCRIPT_OPERATING_SYSTEM_RHEL:'RHEL'}

SUPPORTED_EBS_VOLUME_TYPES = (SCRIPT_EBS_VOLUME_TYPE_STANDARD,
                             SCRIPT_EBS_VOLUME_TYPE_IO1,
                             SCRIPT_EBS_VOLUME_TYPE_GP2,
                             SCRIPT_EBS_VOLUME_TYPE_SC1,
                             SCRIPT_EBS_VOLUME_TYPE_ST1
                             )

EBS_VOLUME_TYPES_MAP = {
                        SCRIPT_EBS_VOLUME_TYPE_STANDARD : {'storageMedia':STORAGE_MEDIA_HDD , 'volumeType':EBS_VOLUME_TYPE_MAGNETIC},
                        SCRIPT_EBS_VOLUME_TYPE_IO1 : {'storageMedia':STORAGE_MEDIA_SSD , 'volumeType':EBS_VOLUME_TYPE_PIOPS}, 
                        SCRIPT_EBS_VOLUME_TYPE_GP2 : {'storageMedia':STORAGE_MEDIA_SSD , 'volumeType':EBS_VOLUME_TYPE_GENERAL_PURPOSE},
                        SCRIPT_EBS_VOLUME_TYPE_SC1 : {'storageMedia':STORAGE_MEDIA_HDD , 'volumeType':EBS_VOLUME_TYPE_MAGNETIC},
                        SCRIPT_EBS_VOLUME_TYPE_ST1 : {'storageMedia':STORAGE_MEDIA_HDD , 'volumeType':EBS_VOLUME_TYPE_MAGNETIC}
                       }





#_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/

#S3

S3_USAGE_GROUP_REQUESTS_TIER_1 = 'S3-API-Tier1'
S3_USAGE_GROUP_REQUESTS_TIER_2 = 'S3-API-Tier2'
S3_USAGE_GROUP_REQUESTS_SIA_TIER1 = 'S3-API-SIA-Tier1'
S3_USAGE_GROUP_REQUESTS_SIA_TIER2 = 'S3-API-SIA-Tier2'
S3_USAGE_GROUP_REQUESTS_SIA_TIER3 = 'S3-API-SIA-Tier3'
S3_USAGE_GROUP_REQUESTS_SIA_RETRIEVAL = 'S3-API-SIA-Retrieval'

S3_STORAGE_CLASS_STANDARD = 'General Purpose'
S3_STORAGE_CLASS_SIA = 'Infrequent Access'
S3_STORAGE_CLASS_GLACIER = 'Archive'
S3_STORAGE_CLASS_REDUCED_REDUNDANCY = 'Non-Critical Data'


SUPPORTED_REQUEST_TYPES = ('GET','POST')

SCRIPT_STORAGE_CLASS_INFREQUENT_ACCESS = 'STANDARD_IA'
SCRIPT_STORAGE_CLASS_STANDARD = 'STANDARD'
SCRIPT_STORAGE_CLASS_GLACIER = 'GLACIER'
SCRIPT_STORAGE_CLASS_REDUCED_REDUNDANCY = 'REDUCED_REDUNDANCY'






SUPPORTED_S3_STORAGE_CLASSES = (SCRIPT_STORAGE_CLASS_STANDARD,
                             SCRIPT_STORAGE_CLASS_INFREQUENT_ACCESS,
                             SCRIPT_STORAGE_CLASS_GLACIER,
                             SCRIPT_STORAGE_CLASS_REDUCED_REDUNDANCY)


