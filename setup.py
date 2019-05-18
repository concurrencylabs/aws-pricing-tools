from setuptools import setup

setup(name='awspricecalculator',
      version='0.1',
      description='AWS Price List calculations',
      url='https://github.com/ConcurrenyLabs/aws-pricing-tools/tree/master/awspricecalculator',
      author='Concurrency Labs',
      author_email='github@concurrencylabs.com',
      license='GNU',
      packages=['awspricecalculator','awspricecalculator.common',
      	'awspricecalculator.awslambda','awspricecalculator.ec2','awspricecalculator.rds', 'awspricecalculator.emr',
                'awspricecalculator.redshift', 'awspricecalculator.s3','awspricecalculator.dynamodb',
                'awspricecalculator.kinesis', 'awspricecalculator.datatransfer'],
      include_package_data=True,
      zip_safe=False)


