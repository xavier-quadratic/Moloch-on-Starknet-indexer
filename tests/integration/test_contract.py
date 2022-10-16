import pymongo
from starknet_py.contract import Contract
from starknet_py.net.account.account_client import AccountClient
from starknet_py.utils.data_transformer.data_transformer import CairoSerializer
from apibara import EventFilter

from ..conftest import Account, IndexerProcessRunner
from .utils import felt_to_str, str_to_felt


async def test_submit_signaling_event(contract: Contract, client: AccountClient):
    title = "Test signaling event"
    # TODO: test description with more than 31 chars
    description = "Test signaling event"

    invoke_result = await contract.functions["submitSignaling"].invoke(
        title=title, description=description, max_fee=10**16
    )
    await invoke_result.wait_for_acceptance()

    transaction_hash = invoke_result.hash
    transaction_receipt = await client.get_transaction_receipt(transaction_hash)

    # Takes events from transaction receipt
    events = transaction_receipt.events

    # Takes an abi of the event which data we want to serialize
    # We can get it from the contract abi
    # TODO Use compiled_contract fixture or contract.data.abi
    emitted_event_abi = {
        "data": [
            {"name": "id", "type": "felt"},
            {"name": "title", "type": "felt"},
            {"name": "description", "type": "felt"},
            {"name": "type", "type": "felt"},
            {"name": "submittedBy", "type": "felt"},
            {"name": "submittedAt", "type": "felt"},
        ],
        "keys": [],
        "name": "ProposalAdded",
        "type": "event",
    }

    # ProposalAdded.emit(id=info.id, title=info.title, description=info.description, type=info.type, submittedBy=info.submittedBy, submittedAt=info.submittedAt);

    # Creates CairoSerializer with contract's identifier manager
    cairo_serializer = CairoSerializer(
        identifier_manager=contract.data.identifier_manager
    )

    # Transforms cairo data to python (needs types of the values and values)
    python_data = cairo_serializer.to_python(
        value_types=emitted_event_abi["data"], values=events[0].data
    )

    # Transforms python data to cairo (needs types of the values and python data)
    _, event_data = cairo_serializer.from_python(
        emitted_event_abi["data"], *python_data
    )
    assert felt_to_str(event_data["title"]) == title
    assert felt_to_str(event_data["description"]) == description


async def test_indexer(
    run_indexer_process: IndexerProcessRunner,
    contract: Contract,
    client: AccountClient,
    mongo_client: pymongo.MongoClient,
):
    filters = [
        EventFilter.from_event_name(
            name="ProposalAdded",
            address=contract.address,
        ),
    ]

    indexer = run_indexer_process(filters)

    await test_submit_signaling_event(contract=contract, client=client)

    mongo_db = mongo_client[indexer.indexer_id]

    import asyncio

    # Wait for apibara to send the events and for the indexer to handle them
    # TODO: find a better way to do that ?
    await asyncio.sleep(5)

    events = list(mongo_db["events"].find())
    assert len(events) == 1

    event = events[0]

    assert event["name"] == "ProposalAdded"
    assert int(event["address"].hex(), 16) == contract.address