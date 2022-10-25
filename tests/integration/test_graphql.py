from .utils import wait_for_graphql
from ..conftest import GraphQLProcessRunner


async def test_server(run_graphql_process: GraphQLProcessRunner):
    db_name = "not_existant"
    run_graphql_process(db_name)
    assert await wait_for_graphql()
