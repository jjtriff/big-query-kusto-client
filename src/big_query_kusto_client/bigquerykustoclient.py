import logging
import os
import uuid
from datetime import timedelta

import pandas as pd
from azure.kusto.data import (
    KustoClient,
)
from azure.kusto.data._models import KustoResultTable
from azure.kusto.data.exceptions import KustoError, KustoApiError, KustoAsyncUsageError
from azure.kusto.data.helpers import dataframe_from_result_table
from tenacity import retry, wait_incrementing, stop_after_attempt

ADX_RECORDS_LIMIT = os.getenv('ADX_RECORDS_LIMIT', 500_000)
ADX_SIZE_IN_BYTES_LIMIT = os.getenv('ADX_SIZE_IN_BYTES_LIMIT', 67_108_864)  # 64MB


class BigQueryKustoClient():
    _kusto: KustoClient
    _page_size: int
    _uuid: str
    _stored_query_prefix: str
    _db: str

    def __init__(self, kusto: KustoClient):
        self._kusto = kusto
        self._page_size = os.getenv('BQKC_PAGE_SIZE', 100_000)
        self._stored_query_prefix = os.getenv('BQKC_SQ_PREFIX', 'BigQueryKustoClient')
        self._uuid = str(uuid.uuid4()).replace('-', '')

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self._drop_stored_query()
            self._kusto.close()
        except KustoError as ex:
            logging.info(ex)
        except KustoAsyncUsageError:
            if self._kusto._aad_helper :
                self._kusto._aad_helper.close_async()
            self._kusto.close()

        if exc_type is not None:
            raise exc_val

    def _drop_stored_query(self):
        drop = '.drop stored_query_result {prefix}{uuid}'.format(
            uuid=self._uuid,
            prefix=self._stored_query_prefix,
        )
        logging.info("Executing " + drop)

        self._kusto.execute_mgmt(self._db, drop)

    def execute_query(self, db, query, optimal_page=False) -> pd.DataFrame:
        if 'order by' not in query:
            raise ValueError('Order for the big query needs to be defined by the user')

        self._db = db

        _ = self._create_stored_query(query)
        if _ is not None:
            return dataframe_from_result_table(_)

        total_rows, total_size = self._get_totals()

        results = self._get_all_results(
            total_rows,
            self._determine_optimal_page_size(total_rows, total_size) if optimal_page else self._page_size
        )

        self._drop_stored_query()

        return results

    def _get_all_results(self, total_rows, page_size, df=None) -> pd.DataFrame:
        # for the size of the page
        start = 1
        end = start + page_size - 1
        while start <= total_rows:
            paged_df = self._get_results_page(end, start)
            df = paged_df if df is None else pd.concat([df, paged_df])

            # until we exhaust the total of rows
            start = end + 1
            end = start + page_size - 1
        return df

    def _get_results_page(self, end, start):
        paged_query = """
stored_query_result('{prefix}{uuid}')
| where bqkcNum between({start} .. {end})        
                """.format(
            uuid=self._uuid,
            prefix=self._stored_query_prefix,
            start=start,
            end=end
        )
        # add them into the dataframe
        paged_response = self._kusto.execute_query(self._db, paged_query)
        return dataframe_from_result_table(paged_response.primary_results[0])

    @retry(
        wait=wait_incrementing(timedelta(seconds=5), increment=timedelta(seconds=5)),
        stop=stop_after_attempt(6),
    )
    def _get_totals(self):
        show = """
.show stored_query_results
| where Name == '{prefix}{uuid}'        
            """.format(
            uuid=self._uuid,
            prefix=self._stored_query_prefix,
        )
        # determine the total amount of rows
        try:
            logging.debug({'msg': 'Trying to get totals', 'query': show})
            response = self._kusto.execute_mgmt(self._db, show)
            total_rows = response.primary_results[0].to_dict().get('data')[0].get('RowCount')
            total_size = response.primary_results[0].to_dict().get('data')[0].get('SizeInBytes')
            logging.debug({'msg': 'We got totals', 'query': show})
            return total_rows, total_size
        except IndexError as e:
            logging.error(f'Unable to retrieve the totals for the executed query. Query: {show}')
            raise

    def _create_stored_query(self, query: str) -> KustoResultTable:
        """
        Returns None when the result of the query has rows, otherwise
        an emtpy, yet formatted with columns dataframe, of 0 rows
        :param query:
        :return: None | pd.DataFrame
        """
        # create the new stored query result
        create = """
.set stored_query_result {prefix}{uuid} with (previewCount = 1) <|{query}
| extend bqkcNum=row_number()""".format(
            uuid=self._uuid,
            prefix=self._stored_query_prefix,
            query=query
        )

        try:
            response = self._kusto.execute_mgmt(self._db, create)
            # check we got a preview
            if 0 == response.primary_results[0].rows_count:
                logging.info('{classname} found 0 records '
                             'on the preview of a query. '
                             'Returning an empty dataframe'
                             .format(classname=self.__class__.__name__))
                logging.debug('The query was `{}`'.format(query))
                return response.primary_results[0]
            return None
        except KustoApiError as e:
            if 'already exists' in str(e):
                return None
            raise

    @staticmethod
    def _determine_optimal_page_size(total_rows, total_size):
        """
        In a simple approach tries to determine the greater page size possible by
        slicing in the middle the value of total size

        >>> BigQueryKustoClient._determine_optimal_page_size(1_500_000, 72_000_000)
        500000

        >>> BigQueryKustoClient._determine_optimal_page_size(400_000, 72_000_000)
        200000

        >>> BigQueryKustoClient._determine_optimal_page_size(1_600_000, 150_000_000)
        400000


        :param total_rows:
        :param total_size:
        :return:
        """
        while total_size > ADX_SIZE_IN_BYTES_LIMIT:
            total_size = total_size // 2
            total_rows = total_rows // 2

        return ADX_RECORDS_LIMIT if total_rows > ADX_RECORDS_LIMIT else total_rows
