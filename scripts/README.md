## Concurrency Labs - aws-pricing-tools scripts

This folder contains Python scripts that are used for various purposes in the repository

All scripts need to be executed from the `/scripts` folder.


Make sure you have the following environment variables set:

```
export AWS_DEFAULT_PROFILE=<your-aws-cli-profile>
export AWS_DEFAULT_REGION=<us-east-1|us-west-2|etc.>
```


### Get Latest Index

The code needs a local copy of the the AWS Price List API index file. 
The GitHub repo doesn't come with the index file, therefore you have to
download it the first time you run a test and every time AWS publishes a new
Price List API index.

In order to download the latest index file, go to the "scripts" folder and run:

```
python get-latest-index.py --service=<ec2|rds|lambda|all>
```

The script takes a few seconds to execute since some index files are a little heavy (like the EC2 one).

I recommend executing with the option `--service=all` and subscribing to the AWS Price List API change notifications.


### Lambda Optimization Recommendations

This script does the following:

* It finds the function's execution records in CloudWatch Logs, for the
given time window in minutes (i.e. the past 10 minutes)
* Parses usage information and extracts memory used, execution time and memory allocated
* It uses the Price List Index to calculate pricing for the Lambda function, 
for different scenarios and tells you potential savings.


```
python lambda-optimization.py --function=<my-function-name> --minutes=<number-of-minutes>
```

This function requires you to have the following IAM permissions:
* `lambda:getFunction`
* `logs:getLogEvents`

Make sure variables AWS_DEFAULT_PROFILE and AWS_DEFAULT_REGION are set.  




