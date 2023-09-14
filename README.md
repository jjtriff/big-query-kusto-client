# big-query-kusto-client

Package to facilitate the gathering of big datasets
from Azure Data Explorer by paginating

## Usage

```python
from bigquerykustoclient import BigQueryKustoClient

# Resolve the KQL client how ever you see fit
kusto = build_kusto_client()

# pass it on the constructor
# and much better using with:

with BigQueryKustoClient(kusto) as client:
    df: pandas.DataFrame = client.execute_query(
        db='ContosoSales',
        query= 'SaltesTable | order by DateKey, ProductKey, CustomerKey',
        optimal_page=True
    )

len(df)  # Will give you the amount of rows it broght for you
```

### Important Note

For this to work it is required that the query imposes an
order on the results, no matter what column you use but an 
`| order by ` operator must be in the query.

## Other considerations

The package uses this other values from the system for its
configuration. It tries to keep sensible defaults:

```properties
ADX_RECORDS_LIMIT=500000  # Limit of amount of rows in ADX
ADX_SIZE_IN_BYTES_LIMIT=67108864  # 64MB limit of size of result
BQKC_PAGE_SIZE=100000  # Default pagesize that we'll use to paginate the results
BQKC_SQ_PREFIX=BigQueryKustoClient  # A prefix that will be used as namespace for the queries
```

`BQKC_PAGE_SIZE` will get overridden if the parameter `optimal_page=True` is used.
When done so, the pacakge will try to determine the biggest possible size of page
to use.

