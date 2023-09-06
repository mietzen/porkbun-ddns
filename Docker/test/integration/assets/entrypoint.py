import os
import logging
from time import sleep
from porkbun_ddns import cli

logger = logging.getLogger('porkbun_ddns')
logger.setLevel(logging.INFO)
logger.propagate = False

sleep_time = int(os.getenv('SLEEP', 300))

logger.info('\n------------------------------------')
logger.info('INTEGRATION TEST!')
logger.info('------------------------------------\n')
while True:
    try:
        cli.main(argv=['-h'])
    except SystemExit:
        pass
    finally:
        logger.info('\n------------------------------------')
        logger.info('Sleeping... {}s'.format(sleep_time))
        logger.info('------------------------------------\n')
        sleep(sleep_time)
