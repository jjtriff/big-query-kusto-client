import os
from unittest import mock
from unittest.mock import patch

import pandas
import pytest
from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
from azure.kusto.data.exceptions import KustoError, KustoAsyncUsageError
from azure.kusto.data.security import _AadHelper

from src.big_query_kusto_client import BigQueryKustoClient

kusto_mock = mock.MagicMock()
kusto_client = None
db_name = 'ContosoSales'
big_query = 'SalesTable'


@pytest.fixture(scope='module', autouse=True)
def setup_and_teardown():
    kusto_client = KustoClient(
        KustoConnectionStringBuilder.with_interactive_login(os.getenv("KUSTO_URI", 'https://help.kusto.windows.net/'))
    )
    yield
    kusto_client.close()


@patch.object(BigQueryKustoClient, '__exit__')
@patch.object(BigQueryKustoClient, '__enter__')
def test_class_works_well_on_with(_enter, _exit):
    with BigQueryKustoClient(kusto_mock) as client:
        _enter.assert_called_once()

    _exit.assert_called_once()


def test_kusto_client_hits_a_big_query(kusto_client):
    with pytest.raises(KustoError) as ex:
        kusto_client.execute_query(database=db_name, query=big_query)

    assert 'E_QUERY_RESULT_SET_TOO_LARGE' in str(ex.value)


def test_class_raises_value_error_when_query_is_not_ordered(kusto_client):
    with pytest.raises(ValueError) as ex:
        client = BigQueryKustoClient(kusto_client)
        client.execute_query(db_name, query=big_query)

    assert 'Order for the big query' in str(ex)


def test_class_returns_empty_df_on_empty_query(kusto_client: KustoClient):
    with BigQueryKustoClient(kusto_client) as client:
        df: pandas.DataFrame = client.execute_query(
            db_name,
            big_query + '|take 0| order by DateKey, ProductKey, CustomerKey'
        )

    assert len(df) == 0


def test_class_manages_big_query_successfully(kusto_client: KustoClient):
    response = kusto_client.execute_query(db_name, big_query + '| count')
    row_total = response.primary_results[0].to_dict().get('data')[0].get('Count')

    with BigQueryKustoClient(kusto_client) as client:
        df: pandas.DataFrame = client.execute_query(db_name, big_query + '| order by DateKey, ProductKey, CustomerKey')

    assert len(df) == row_total


def test_class_manages_big_query_successfully_optimal(kusto_client: KustoClient):
    response = kusto_client.execute_query(db_name, big_query + '| count')
    row_total = response.primary_results[0].to_dict().get('data')[0].get('Count')

    with BigQueryKustoClient(kusto_client) as client:
        df: pandas.DataFrame = client.execute_query(
            db_name,
            big_query + '| order by DateKey, ProductKey, CustomerKey',
            optimal_page=True
        )

    assert len(df) == row_total


def test_class_manages_repeat_calls_gracefully(kusto_client: KustoClient):
    row_total = 100
    # noinspection PyTypeChecker
    df: pandas.DataFrame = None
    with BigQueryKustoClient(kusto_client) as client:
        for _ in range(2):
            df = client.execute_query(
                db_name,
                big_query + f'| take {row_total} ' + '| order by DateKey, ProductKey, CustomerKey',
                optimal_page=True
            )

    assert len(df) == row_total


@pytest.fixture
def kusto_client() -> KustoClient:
    return KustoClient(
        KustoConnectionStringBuilder.with_interactive_login(os.getenv("KUSTO_URI", 'https://help.kusto.windows.net/'))
    )


def test_class_closes_async_kusto_clients_successfully(kusto_client: KustoClient):
    row_total = 100
    # noinspection PyTypeChecker
    df: pandas.DataFrame = None
    try:
        with BigQueryKustoClient(kusto_client) as client:
            for _ in range(2):
                df = client.execute_query(
                    db_name,
                    big_query + f'| take {row_total} ' + '| order by DateKey, ProductKey, CustomerKey',
                    optimal_page=True
                )

            kusto_client._aad_helper = _AadHelper(kusto_client._kcsb, True)

        assert len(df) == row_total
    except KustoAsyncUsageError as e:
        assert False, "Exception was thrown for async kusto client"
