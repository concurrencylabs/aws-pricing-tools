import consts
from errors import ValidationError



class ElbPriceDimension():
    def __init__(self, hours, dataProcessedGb):
        self.hours = hours
        self.dataProcessedGb = dataProcessedGb

class Ec2PriceDimension():
    def __init__(self, **kargs):

      """
      region, instance_type, instance_hours, operating_system, data_transfer_out_internet_gb,
                 data_transfer_out_intraregion_gb, data_transfer_out_inter_region_gb, to_region, piops, ebs_volume_type,
                 ebs_storage_gb_month, ebs_snapshot_gb_month, elb_hours, elb_data_processed_gb
      """

      self.region = kargs['region']
      self.instanceType = ''
      if 'instanceType' in kargs: self.instanceType = kargs['instanceType']
      self.instanceHours = 0
      if 'instanceHours' in kargs: self.instanceHours = kargs['instanceHours']
      self.operatingSystem = consts.SCRIPT_OPERATING_SYSTEM_LINUX
      if 'operatingSystem' in kargs: self.operatingSystem = kargs['operatingSystem']
      self.dataTransferOutInternetGb = 0
      if 'dataTransferOutInternetGb' in kargs: self.dataTransferOutInternetGb = kargs['dataTransferOutInternetGb']
      self.dataTransferOutIntraRegionGb = 0
      if 'dataTransferOutIntraregionGb' in kargs: self.dataTransferOutIntraRegionGb = kargs['dataTransferOutIntraregionGb']
      self.dataTransferOutInterRegionGb = 0
      if 'dataTransferOutInterRegionGb' in kargs: self.dataTransferOutInterRegionGb = kargs['dataTransferOutInterRegionGb']
      self.toRegion = ''
      if 'toRegion' in kargs: self.toRegion = kargs['toRegion']
      self.pIops = 0
      if 'piops' in kargs: self.pIops = kargs['piops']
      self.storageMedia = ''
      ebs_volume_type = ''
      if 'ebsVolumeType' in kargs: ebs_volume_type = kargs['ebsVolumeType']
      if ebs_volume_type in consts.EBS_VOLUME_TYPES_MAP: self.storageMedia = consts.EBS_VOLUME_TYPES_MAP[ebs_volume_type]['storageMedia']
      self.volumeType = ''
      if ebs_volume_type in consts.EBS_VOLUME_TYPES_MAP: self.volumeType = consts.EBS_VOLUME_TYPES_MAP[ebs_volume_type]['volumeType']
      if not self.volumeType: self.volumeType = consts.SCRIPT_EBS_VOLUME_TYPE_GP2
      self.ebsStorageGbMonth = 0
      if 'ebsStorageGbMonth' in kargs: self.ebsStorageGbMonth = kargs['ebsStorageGbMonth']
      self.ebsSnapshotGbMonth = 0
      if 'ebsSnapshotGbMonth' in kargs: self.ebsSnapshotGbMonth = kargs['ebsSnapshotGbMonth']
      self.elbHours = 0
      if 'elbHours' in kargs: self.elbHours = kargs['elbHours']
      self.elbDataProcessedGb = 0
      if 'elbDataProcessedGb' in kargs: self.elbDataProcessedGb = kargs['elbDataProcessedGb']


      #TODO: Add support for shared and dedicated tenancies
      self.tenancy = consts.EC2_TENANCY_SHARED

    def validate(self):
      validation_ok = True
      validation_message = ""

      if self.instanceType and self.instanceType not in consts.SUPPORTED_INSTANCE_TYPES:
        validation_message = "instance-type must be one of the following values:"+str(consts.SUPPORTED_INSTANCE_TYPES)
        validation_ok = False
      if self.region not in consts.SUPPORTED_REGIONS:
        validation_message = "region must be one of the following values:"+str(consts.SUPPORTED_REGIONS)
        validation_ok = False
      if self.operatingSystem and self.operatingSystem not in consts.SUPPORTED_EC2_OPERATING_SYSTEMS:
        validation_message = "operating-system must be one of the following values:"+str(consts.SUPPORTED_EC2_OPERATING_SYSTEMS)
        validation_ok = False
      if self.ebsVolumeType and self.ebsVolumeType not in consts.SUPPORTED_EBS_VOLUME_TYPES:
        validation_message = "ebs-volume-type must be one of the following values:"+str(consts.SUPPORTED_EBS_VOLUME_TYPES)
        validation_ok = False
      if self.dataTransferOutInterRegionGb and self.toRegion not in consts.SUPPORTED_REGIONS:
        validation_message = "to-region must be one of the following values:"+str(consts.SUPPORTED_REGIONS)
      if self.dataTransferOutInterRegionGb and self.region == self.toRegion:
        validation_message = "source and destination regions must be different for inter-regional data transfers"
      #TODO: add validation for max number of IOPS
      #TODO: add validation for negative numbers

      if not validation_ok:
          raise ValidationError(validation_message)

      return





class RdsPriceDimension():
    def __init__(self, **kargs):
      self.region = ''
      if 'region' in kargs: self.region = kargs['region']

      self.dbInstanceClass = ''
      if 'dbInstanceClass' in kargs: self.dbInstanceClass = kargs['dbInstanceClass']

      self.engine = ''
      if 'engine' in kargs: self.engine = kargs['engine']

      self.licenseModel = ''
      if 'licenseModel' in kargs: self.licenseModel = kargs['licenseModel']
      if self.engine in (consts.SCRIPT_RDS_DATABASE_ENGINE_MYSQL,consts.SCRIPT_RDS_DATABASE_ENGINE_POSTGRESQL, consts.SCRIPT_RDS_DATABASE_ENGINE_AURORA):
          self.licenseModel = consts.SCRIPT_RDS_LICENSE_MODEL_PUBLIC

      self.instanceHours = 0
      if 'instanceHours' in kargs: self.instanceHours = kargs['instanceHours']

      self.multiAz = False
      if 'multiAz' in kargs: self.multiAz = kargs['multiAz']

      if self.multiAz:
        self.deploymentOption = consts.RDS_DEPLOYMENT_OPTION_MULTI_AZ
      else:
        self.deploymentOption = consts.RDS_DEPLOYMENT_OPTION_SINGLE_AZ

      self.internetDataTransferOutGb = 0
      if 'internetDataTransferOutGb' in kargs: self.internetDataTransferOutGb = kargs['internetDataTransferOutGb']

      self.interRegionDataTransferGb = 0
      if 'interRegionDataTransferGb' in kargs: self.interRegionDataTransferGb = kargs['interRegionDataTransferGb']

      self.storageGbMonth = 0
      if 'storageGbMonth' in kargs: self.storageGbMonth = kargs['storageGbMonth']

      self.storageType = ''
      if 'storageType' in kargs: self.storageType = kargs['storageType']

      self.volumeType = self.calculate_volume_type()

      self.iops = 0
      if 'iops' in kargs: self.iops= kargs['iops']

      self.ioRate = 0
      if 'ioRate' in kargs: self.ioRate= kargs['ioRate']


      """

      backupStorageGbMonth = 0
      if 'backupStorageGbMonth' in kwargs: backupStorageGbMonth = kwargs['backupStorageGbMonth']
      """

      self.validate()



    def calculate_volume_type(self):
      #TODO:add condition for Aurora
      if self.storageType in consts.RDS_VOLUME_TYPES_MAP:
        return consts.RDS_VOLUME_TYPES_MAP[self.storageType]

    def validate(self):
      validation_ok = True
      validation_message = ""
      valid_engine = True

      if self.dbInstanceClass and self.dbInstanceClass not in consts.SUPPORTED_RDS_INSTANCE_CLASSES:
        validation_message = "\n" + "db-instance-class must be one of the following values:"+str(consts.SUPPORTED_RDS_INSTANCE_CLASSES)
      if self.region not in consts.SUPPORTED_REGIONS:
        validation_message += "\n" + "region must be one of the following values:"+str(consts.SUPPORTED_REGIONS)
      if self.engine and self.engine not in consts.RDS_SUPPORTED_DB_ENGINES:
        validation_message += "\n" + "engine must be one of the following values:"+str(consts.RDS_SUPPORTED_DB_ENGINES)
        valid_engine  = False
      if valid_engine and self.engine not in (consts.SCRIPT_RDS_DATABASE_ENGINE_MYSQL,consts.SCRIPT_RDS_DATABASE_ENGINE_POSTGRESQL, consts.SCRIPT_RDS_DATABASE_ENGINE_AURORA):
        if self.licenseModel and self.licenseModel not in (consts.RDS_SUPPORTED_LICENSE_MODELS):
          validation_message += "\n" + "license-model must be one of the following values:"+str(consts.RDS_SUPPORTED_LICENSE_MODELS)
      if self.storageType:
        if self.storageType not in consts.SUPPORTED_RDS_STORAGE_TYPES:
          validation_message += "\n" + "storage-type must be one of the following values:"+str(consts.SUPPORTED_RDS_STORAGE_TYPES)
        if self.storageType == consts.SCRIPT_RDS_STORAGE_TYPE_IO1 and not self.iops:
          validation_message += "\n" + "you must specify an iops value for storage type io1"

      if validation_message:
          print "Error: [{}]".format(validation_message)
          raise ValidationError(validation_message)

      return




class LambdaPriceDimension():
    def __init__(self,region, request_count, avg_duration_ms, memory_mb,  data_tranfer_out_internet_gb,
                 data_transfer_out_intra_region_gb, data_transfer_out_inter_region_gb, to_region):
        self.region = region
        self.requestCount = request_count
        self.avgDurationMs = avg_duration_ms
        self.memoryMb = memory_mb
        self.dataTransferOutInternetGb = data_tranfer_out_internet_gb
        self.dataTransferOutIntraRegionGb = data_transfer_out_intra_region_gb
        self.dataTransferOutInterRegionGb = data_transfer_out_inter_region_gb
        self.toRegion = to_region
        self.validate()

    def validate(self):
        validation_ok = True
        validation_message = ""
        if not self.region:
            validation_message = "Region must be specified"
            validation_ok = False
        if self.region not in consts.SUPPORTED_REGIONS:
            validation_message = "Region must be one of the following:"+str(consts.SUPPORTED_REGIONS)
            validation_ok = False
        if self.requestCount == 0 and (self.avgDurationMs > 0 or self.memoryMb > 0):
            validation_message = "Cannot have value for average duration or memory if requestCount is zero"
            validation_ok = False
        if self.dataTransferOutInterRegionGb > 0 and not self.toRegion:
            validation_message = "Must specify a to-region if you specify data-transfer-out-interregion_gb"
            validation_ok = False
        if not validation_ok:
            raise ValidationError(validation_message)

        return






"""
This object represents the total price calculation.
It includes an array of PricingRecord objects, which are a breakdown of how the price is calculated
"""
class PricingResult():
    def __init__(self, awsPriceListApiVersion, region, total_cost, pricing_records):
        total_cost = round(total_cost,2)
        self.version = "v1.0"
        self.awsPriceListApiVersion = awsPriceListApiVersion
        self.region = region
        self.totalCost = total_cost
        self.currency = consts.DEFAULT_CURRENCY
        self.pricingRecords = pricing_records

class PricingRecord():
    def __init__(self, service, amt, desc, pricePerUnit, usgUnits, rateCode):
        usgUnits = round(float(usgUnits),2)
        amt = round(amt,2)
        self.service = service
        #self.resourceId = resourceId  #leaving for future use
        #self.periodStart = start
        #self.periodEnd = end
        self.amount = amt
        self.description = desc
        self.pricePerUnit = pricePerUnit
        self.usageUnits = int(usgUnits)
        self.rateCode = rateCode


#Desired JSON output returned by the funcion

"""
  {
    "version:"v1.0",
    "awsPriceListApiVersion":"20160812001705"
    "region":"us-east-1",
    "currency":"USD",
    "pricingRecords":[{
      "service":"elb",
      "amount":"12.33",
      "description":"$0.013 per On Demand Linux t2.micro Instance Hour",
      "pricePerUnit":"0.013",
      "usageUnits":"720",
      "rateCode":"HZC9FAP4F9Y8JW67.JRTCKXETXF.6YS6EN2CT7"
      }
    ]




  }

"""

