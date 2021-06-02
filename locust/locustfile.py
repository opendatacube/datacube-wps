import time

import requests
import xmltodict
from gevent.pool import Pool

from locust import HttpUser, between, task


class WPS(HttpUser):
    wait_time = between(60, 120)

    @task()
    def post_request(self):
        data = get_test_data()

        with self.client.post("/wps/?service=WPS&request=Execute", data=data) as response:
            def check_s3_status():
                s3_location = get_s3_location(response.content)
                process_succeeded(s3_location)
            pool = Pool()
            pool.spawn(check_s3_status)
            pool.join()

            if not response.status_code == 200:
                errormsg = f"Request failed with HTTP status code: {response.status_code}\n Request URL: {response.url}\n Response-Content: {response.text}"
                print( f"Request failed:\n {errormsg}" )
                return


def process_succeeded(s3_location):
        data = requests.get(s3_location)
        response = xmltodict.parse(data.text)

        start_time = time.time()
        seconds = 150

        while True:
            current_time = time.time()
            elapsed_time = current_time - start_time

            time.sleep(2)
            data = requests.get(s3_location)
            response = xmltodict.parse(data.text)
            status = response['wps:ExecuteResponse']['wps:Status']

            print(f'Processing {s3_location.split("/")[-1]}')
            if 'wps:ProcessSucceeded' in status:
                print("***** Succeeded *****")
                break

            if elapsed_time > seconds:
                print(f"Failed to process {s3_location}")
                with open('/mnt/locust/failures.txt', 'a') as writer:
                    writer.write(f'{s3_location}\n')
                break

def get_s3_location(content):
    data = content.decode()
    response = xmltodict.parse(data)
    s3_location = response['wps:ExecuteResponse']['@statusLocation']
    return s3_location


def get_test_data():
    with open('/mnt/locust/request_data.xml', 'r') as xml_fh:
        data = xml_fh.read()
    return data





# https://ows.dev.dea.ga.gov.au/wps/?service=WPS&request=Execute