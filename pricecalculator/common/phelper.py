
import consts



def is_data_transfer_out_internet(sku_data):
  result = False
  if sku_data['attributes']['servicecode'] == consts.SERVICE_CODE_AWS_DATA_TRANSFER\
    and sku_data['attributes']['toLocation'] == 'External'\
    and sku_data['attributes']['transferType'] == 'AWS Outbound':
    result = True

  return result


def is_data_transfer_intraregional(sku_data):
  result = False
  if sku_data['attributes']['servicecode'] == consts.SERVICE_CODE_AWS_DATA_TRANSFER\
    and sku_data['attributes']['transferType'] == 'IntraRegion':
    result = True

  return result


def is_data_transfer_interregional(sku_data, toRegion):
  result = False
  if sku_data['attributes']['servicecode'] == consts.SERVICE_CODE_AWS_DATA_TRANSFER\
    and sku_data['attributes']['transferType'] == 'InterRegion Outbound':
      if sku_data['attributes']['toLocation'] == consts.REGION_MAP[toRegion]:
        result = True

  return result





def getBillableBand(priceDimensions, usageAmount):
  billableBand = 0
  beginRange = int(priceDimensions['beginRange'])
  endRange = priceDimensions['endRange']
  pricePerUnit = priceDimensions['pricePerUnit']['USD']
  if endRange == consts.INFINITY:
    if beginRange < usageAmount:
      billableBand = usageAmount - beginRange
  else:
    endRange = int(endRange)
    if endRange >= usageAmount and beginRange < usageAmount:
      billableBand = usageAmount - beginRange
    if endRange < usageAmount: 
      billableBand = endRange - beginRange
  return billableBand


#TODO: filter by active records
def get_price_dimensions(term_data):
  pdims = []
  for offer_term in term_data:
    for tk in offer_term:
      #print(str(list(offer_term[tk]['priceDimensions'])))
      for pdk in list(offer_term[tk]['priceDimensions']):
        pdims.append(offer_term[tk]['priceDimensions'][pdk])
  
  #print("price_dimensions: "+json.dumps(pdims,sort_keys=True,indent=4, separators=(',', ': ')))
  return pdims



def get_terms(price_data, skus, **kwargs):
  terms = []
  type = kwargs['type']
  #terms = [price_data['terms'][type][k] for k in skus]
  for k in skus:
    if k in price_data['terms'][type]:
      terms.append(price_data['terms'][type][k])
  #print("terms: "+json.dumps(terms,sort_keys=True,indent=4, separators=(',', ': ')))
  return terms
  

def get_skus(price_data, **kwargs):
  skus = []
  region = kwargs['region']
  for p in get_products(price_data):
    region_attr_key = get_region_attr_key(p)
    if region_attr_key in p['attributes']:
      if consts.REGION_MAP[region] == p['attributes'][region_attr_key]: skus.append(p['sku'])

  #print ("skus: " + str(skus))
  return skus

  
def get_product_families(price_data, **kwargs):
  pfamilies = []
  region = kwargs['region']
  #print("products: "+json.dumps(get_products(price_data),sort_keys=True,indent=4, separators=(',', ': ')))  
  for p in get_products(price_data):
    region_attr_key = get_region_attr_key(p)
    if region_attr_key in p['attributes']:
      if consts.REGION_MAP[region] == p['attributes'][region_attr_key]:
        if p['productFamily'] not in pfamilies: pfamilies.append(p['productFamily'])
    #else:
      #print("Product without location attribute: \n"+json.dumps(p,sort_keys=True,indent=4, separators=(',', ': ')))


  #print ("families: " + str(pfamilies))
  return pfamilies


"""
This method gets a list of distinct product attributes, such as 'storageMedia', 'volumeType', etc.
It's useful for making sure the code is evaluating all existing combinations that may incur in a charge
"""

def get_distinct_product_attributes(price_data, attribute, **kwargs):
  distinctattributes = []
  region = kwargs['region']
  #print("products: "+json.dumps(get_products(price_data),sort_keys=True,indent=4, separators=(',', ': ')))
  for p in get_products(price_data):
    region_attr_key = get_region_attr_key(p)
    if region_attr_key in p['attributes']:
      if consts.REGION_MAP[region] == p['attributes'][region_attr_key]:
        if attribute in p['attributes']:
          if p['attributes'][attribute] not in distinctattributes: distinctattributes.append(p['attributes'][attribute])
    #else:
      #print("Product without location attribute: \n"+json.dumps(p,sort_keys=True,indent=4, separators=(',', ': ')))


  print ("Distinct values for attribute ["+attribute+"]: " + str(distinctattributes))
  return distinctattributes






def get_products(price_data):
  return [price_data['products'][k] for k in price_data['products']]


"""
Region Atribute varies according to the type of record
- Data Transfer (from and to)

"""

def get_region_attr_key(product):
  region_attr_key = 'location'
  if 'servicecode' in product['attributes']:
    if product['attributes']['servicecode'] == consts.SERVICE_CODE_AWS_DATA_TRANSFER:
      region_attr_key = 'fromLocation'
  return region_attr_key




#Creates a table with all the SKUs that are part of the total price
def buildSkuTable(evaluated_sku_desc):
  result = {}
  sorted_descriptions = sorted(evaluated_sku_desc)
  result_table_header = "Price | Description | Price Per Unit | Usage | Rate Code"
  result_records = ""
  total = 0
  for s in sorted_descriptions:
    result_records = result_records + "$" + str(s[0]) + "|" + str(s[1]) + "|" + str(s[2]) + "|" + str(s[3]) + "|" + s[4]+"\n"
    total = total + s[0]
  
  result['header']=result_table_header
  result['records']=result_records
  result['total']=total
  return result










