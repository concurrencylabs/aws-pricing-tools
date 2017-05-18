import consts
from errors import ValidationError



class ElbPriceDimension():
    def __init__(self, hours, dataProcessedGb):
        self.hours = hours
        self.dataProcessedGb = dataProcessedGb



class S3PriceDimension():
    def __init__(self, **kwargs):
          self.region = ''
          self.termType = consts.SCRIPT_TERM_TYPE_ON_DEMAND
          self.storageClass = ''
          self.storageSizeGb = 0
          self.requestType = ''
          self.requestNumber = 0
          self.dataRetrievalGb = 0
          self.dataTransferOutInternetGb = 0

          if 'region' in kwargs: self.region = kwargs['region']
          if 'storageClass' in kwargs: self.storageClass = kwargs['storageClass']
          if 'storageSizeGb' in kwargs: self.storageSizeGb = kwargs['storageSizeGb']
          if 'requestType' in kwargs: self.requestType = kwargs['requestType']
          if 'requestNumber' in kwargs: self.requestNumber = kwargs['requestNumber']
          if 'dataRetrievalGb' in kwargs: self.dataRetrievalGb = kwargs['dataRetrievalGb']
          if 'dataTransferOutInternetGb' in kwargs: self.dataTransferOutInternetGb = kwargs['dataTransferOutInternetGb']


          self.validate()


    def validate(self):
      validation_ok = True
      validation_message = ""

      if self.storageClass and self.storageClass not in consts.SUPPORTED_S3_STORAGE_CLASSES:
        validation_message += "Invalid storage class:["+self.storageClass+"]\n"
        validation_ok = False
      if self.region not in consts.SUPPORTED_REGIONS:
        validation_message += "Invalid region:["+self.region+"]\n"
        validation_ok = False
      if self.requestType and self.requestType not in consts.SUPPORTED_REQUEST_TYPES:
        validation_message += "Invalid request type:["+self.requestType+"]\n"
        validation_ok = False

      if not validation_ok:
          raise ValidationError(validation_message)

      return validation_ok




class Ec2PriceDimension():
    def __init__(self, **kargs):

      #print "kargs {}".format(kargs)

      self.region = kargs['region']
      self.termType = consts.SCRIPT_TERM_TYPE_ON_DEMAND
      if 'termType' in kargs: self.termType = kargs['termType']

      self.purchaseOption = ''
      if 'purchaseOption' in kargs: self.purchaseOption = kargs['purchaseOption']

      self.offeringClass = ''
      if 'offeringClass' in kargs: self.offeringClass = kargs['offeringClass']

      self.instanceType = ''
      if 'instanceType' in kargs: self.instanceType = kargs['instanceType']
      self.instanceHours = 0
      if 'instanceHours' in kargs: self.instanceHours = kargs['instanceHours']
      self.operatingSystem = consts.SCRIPT_OPERATING_SYSTEM_LINUX
      if 'operatingSystem' in kargs: self.operatingSystem = kargs['operatingSystem']

      #TODO: Add support for pre-installed software (i.e. SQL Web in Windows instances)
      self.preInstalledSoftware = 'NA'

      #TODO: Add support for different license models
      self.licenseModel = consts.SCRIPT_EC2_LICENSE_MODEL_NONE_REQUIRED
      if self.operatingSystem == consts.SCRIPT_OPERATING_SYSTEM_WINDOWS:
          self.licenseModel = consts.SCRIPT_EC2_LICENSE_MODEL_INCLUDED
      if self.operatingSystem == consts.SCRIPT_OPERATING_SYSTEM_WINDOWS_BYOL:
          self.licenseModel = consts.SCRIPT_EC2_LICENSE_MODEL_BYOL




      self.dataTransferOutInternetGb = 0
      if 'dataTransferOutInternetGb' in kargs: self.dataTransferOutInternetGb = kargs['dataTransferOutInternetGb']
      self.dataTransferOutIntraRegionGb = 0
      if 'dataTransferOutIntraRegionGb' in kargs: self.dataTransferOutIntraRegionGb = kargs['dataTransferOutIntraRegionGb']
      self.dataTransferOutInterRegionGb = 0
      if 'dataTransferOutInterRegionGb' in kargs: self.dataTransferOutInterRegionGb = kargs['dataTransferOutInterRegionGb']
      self.toRegion = ''
      if 'toRegion' in kargs: self.toRegion = kargs['toRegion']
      self.pIops = 0
      if 'pIops' in kargs: self.pIops = kargs['pIops']
      self.storageMedia = ''
      self.ebsVolumeType = ''
      if 'ebsVolumeType' in kargs: self.ebsVolumeType = kargs['ebsVolumeType']
      if self.ebsVolumeType in consts.EBS_VOLUME_TYPES_MAP: self.storageMedia = consts.EBS_VOLUME_TYPES_MAP[self.ebsVolumeType]['storageMedia']
      self.volumeType = ''
      if self.ebsVolumeType in consts.EBS_VOLUME_TYPES_MAP:  self.volumeType = consts.EBS_VOLUME_TYPES_MAP[self.ebsVolumeType]['volumeType']
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

      self.validate()

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

      if self.termType not in consts.SUPPORTED_TERM_TYPES:
          validation_message = "term-type must be one of the following values:[{}]".format(consts.SUPPORTED_TERM_TYPES)

      if self.termType == consts.SCRIPT_TERM_TYPE_RESERVED:
          if not self.offeringClass:
              validation_message = "offering-class must be specified for Reserved instances"
          if not self.purchaseOption:
              validation_message = "purchase-option must be specified for Reserved instances"


      #TODO: add validation for max number of IOPS
      #TODO: add validation for negative numbers

      if not validation_ok:
          raise ValidationError(validation_message)

      return validation_ok



class RdsPriceDimension():
    def __init__(self, **kargs):
      self.region = ''
      if 'region' in kargs: self.region = kargs['region']

      self.termType = consts.SCRIPT_TERM_TYPE_ON_DEMAND

      self.dbInstanceClass = ''
      if 'dbInstanceClass' in kargs: self.dbInstanceClass = kargs['dbInstanceClass']

      self.engine = ''
      if 'engine' in kargs: self.engine = kargs['engine']

      self.licenseModel = ''
      if 'licenseModel' in kargs: self.licenseModel = kargs['licenseModel']
      if self.engine in (consts.SCRIPT_RDS_DATABASE_ENGINE_MYSQL,consts.SCRIPT_RDS_DATABASE_ENGINE_POSTGRESQL, consts.SCRIPT_RDS_DATABASE_ENGINE_AURORA):
          self.licenseModel = consts.SCRIPT_RDS_LICENSE_MODEL_PUBLIC

      self.instanceHours = 0
      if 'instanceHours' in kargs: self.instanceHours = int(kargs['instanceHours'])

      self.multiAz = False
      if 'multiAz' in kargs: self.multiAz = kargs['multiAz']

      if self.multiAz:
        self.deploymentOption = consts.RDS_DEPLOYMENT_OPTION_MULTI_AZ
      else:
        self.deploymentOption = consts.RDS_DEPLOYMENT_OPTION_SINGLE_AZ

      self.dataTransferOutInternetGb = 0
      if 'dataTransferOutInternetGb' in kargs: self.dataTransferOutInternetGb = kargs['dataTransferOutInternetGb']
      self.dataTransferOutIntraRegionGb = 0
      if 'dataTransferOutIntraRegionGb' in kargs: self.dataTransferOutIntraRegionGb = kargs['dataTransferOutIntraRegionGb']
      self.dataTransferOutInterRegionGb = 0
      if 'dataTransferOutInterRegionGb' in kargs: self.dataTransferOutInterRegionGb = kargs['dataTransferOutInterRegionGb']
      self.toRegion = ''
      if 'toRegion' in kargs: self.toRegion = kargs['toRegion']

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
      #TODO: add validations for data transfer
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
    def __init__(self,**kargs):

        #print("LambdaPriceDimention args:{}".format(kargs))

        self.region = ''
        self.region = kargs['region']

        self.termType = consts.SCRIPT_TERM_TYPE_ON_DEMAND

        self.requestCount = 0
        if  'requestCount' in kargs: self.requestCount = kargs['requestCount']

        self.avgDurationMs = 0
        if 'avgDurationMs' in kargs: self.avgDurationMs = kargs['avgDurationMs']

        self.memoryMb = 0
        if 'memoryMb' in kargs: self.memoryMb = kargs['memoryMb']

        self.dataTransferOutInternetGb = 0
        if 'dataTransferOutInternetGb' in kargs: self.dataTransferOutInternetGb = kargs['dataTransferOutInternetGb']

        self.dataTransferOutIntraRegionGb = 0
        if  'dataTransferOutIntraRegionGb' in kargs: self.dataTransferOutIntraRegionGb = kargs['dataTransferOutIntraRegionGb']

        self.dataTransferOutInterRegionGb = 0
        if 'dataTransferOutInterRegionGb' in kargs: self.dataTransferOutInterRegionGb = kargs['dataTransferOutInterRegionGb']

        self.toRegion = ''
        if 'toRegion' in kargs: self.toRegion = kargs['toRegion']

        self.validate()


    def validate(self):
        validation_message = ""
        if not self.region:
            validation_message += "Region must be specified\n"
        if self.region not in consts.SUPPORTED_REGIONS:
            validation_message += "Region must be one of the following:"+str(consts.SUPPORTED_REGIONS)
        if self.requestCount and self.avgDurationMs == 0:
            validation_message += "Cannot have value for requestCount and avgDurationMs=0\n"
        if self.requestCount and self.memoryMb== 0:
            validation_message += "Cannot have value for requestCount and memoryMb=0\n"
        if self.requestCount == 0 and (self.avgDurationMs > 0 or self.memoryMb > 0):
            validation_message += "Cannot have value for average duration or memory if requestCount is zero\n"
        if self.dataTransferOutInterRegionGb > 0 and not self.toRegion:
            validation_message += "Must specify a to-region if you specify data-transfer-out-interregion-gb\n"

        if validation_message:
            print("Error: [{}]".format(validation_message))
            raise ValidationError(validation_message)

        return


"""
This object represents the total price calculation.
It includes an array of PricingRecord objects, which are a breakdown of how the price is calculated
"""
class PricingResult():
    def __init__(self, awsPriceListApiVersion, region, total_cost, pricing_records):
        total_cost = round(total_cost,2)
        self.version = "v2.0"
        self.awsPriceListApiVersion = awsPriceListApiVersion
        self.region = region
        self.totalCost = round(total_cost,2)
        self.currency = consts.DEFAULT_CURRENCY
        self.pricingRecords = pricing_records

class PricingRecord():
    def __init__(self, service, amt, desc, pricePerUnit, usgUnits, rateCode):
        usgUnits = round(float(usgUnits),2)
        amt = round(amt,2)
        self.service = service
        self.amount = amt
        self.description = desc
        self.pricePerUnit = pricePerUnit
        self.usageUnits = int(usgUnits)
        self.rateCode = rateCode

