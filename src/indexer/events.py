"""Inherit from `Event` to get a free `from_starknet_event` method that creates
in instance from a `StarkNetEvent`, the from_starknet_event method uses the type hints
given in the dataclass to know how to deserialize the values
"""

from dataclasses import dataclass, asdict
import logging
from typing import Type

from apibara import Info
from apibara.model import BlockHeader, StarkNetEvent

from indexer.utils import get_block_datetime_utc
from .deserializer import BlockNumber
from .models import ProposalStatus


logger = logging.getLogger(__name__)


@dataclass
class Event:
    async def _write_to_events_collection(
        self, info: Info, block: BlockHeader, starknet_event: StarkNetEvent
    ):
        logger.debug("Inserting to 'events': %s", self)
        await info.storage.insert_one("events", asdict(self))

    async def _handle(
        self, info: Info, block: BlockHeader, starknet_event: StarkNetEvent
    ):
        logger.warning(f"No custom _handle implemented for {self.__class__.__name__}")

    async def handle(
        self, info: Info, block: BlockHeader, starknet_event: StarkNetEvent
    ):
        await self._write_to_events_collection(info, block, starknet_event)
        await self._handle(info, block, starknet_event)


async def update_proposal(
    id: int,
    document: dict,
    info: Info,
    block: BlockHeader,
    starknet_event: StarkNetEvent,
):
    logger.debug("Updating proposal %s with %s", id, document)
    existing = await info.storage.find_one_and_update(
        collection="proposals",
        filter={"id": id},
        update={"$set": document},
    )
    logger.debug("Existing proposal %s", existing)


@dataclass
class ProposalAdded(Event):
    id: int
    title: str
    type: str
    description: str
    submittedAt: BlockNumber
    submittedBy: bytes

    async def _handle(
        self, info: Info, block: BlockHeader, starknet_event: StarkNetEvent
    ):
        proposal_dict = {
            **asdict(self),
            "status": ProposalStatus.SUBMITTED.value,
            "statusHistory": [
                (
                    ProposalStatus.SUBMITTED.value,
                    get_block_datetime_utc(block),
                )
            ],
        }
        logger.debug("Inserting ProposalAdded(%s)", proposal_dict)
        await info.storage.insert_one("proposals", proposal_dict)

        proposal_params = await info.storage.find_one(
            "proposal_params", {"type": self.type}
        )

        if proposal_params is None:
            # TODO: find a better / more specific exception class
            raise Exception(
                f"Cannot find proposal params(majority, quorum ...) for type"
                f" '{self.type}' in 'proposal_params' collection, check if the"
                f" indexer is handling ProposalParamsUpdated events"
            )

        del proposal_params["_id"]

        logger.debug("Updating proposal %s", self)
        existing = await info.storage.find_one_and_update(
            collection="proposals",
            filter={"id": self.id},
            update={"$set": proposal_params},
        )
        logger.debug("Existing proposal %s", existing)


@dataclass
class ProposalParamsUpdated(Event):
    type: str
    majority: int
    quorum: int
    votingDuration: int
    graceDuration: int

    async def handle(
        self, info: Info, block: BlockHeader, starknet_event: StarkNetEvent
    ):
        logger.debug("Inserting %s", self)
        await info.storage.insert_one("proposal_params", asdict(self))


@dataclass
class OnboardProposalAdded(Event):
    id: int
    applicantAddress: bytes
    shares: int
    loot: int
    tributeOffered: int
    tributeAddress: bytes

    async def _handle(
        self, info: Info, block: BlockHeader, starknet_event: StarkNetEvent
    ):

        return await update_proposal(
            id=self.id,
            document=asdict(self),
            info=info,
            block=block,
            starknet_event=starknet_event,
        )


@dataclass
class ProposalStatusUpdated(Event):
    id: int
    status: int

    async def _handle(
        self, info: Info, block: BlockHeader, starknet_event: StarkNetEvent
    ):
        await update_proposal(
            id=self.id,
            document=asdict(self),
            info=info,
            block=block,
            starknet_event=starknet_event,
        )

        await info.storage.find_one_and_update(
            collection="proposals",
            filter={"id": self.id},
            update={
                "$push": {
                    "statusHistory": (
                        ProposalStatus(self.status).value,
                        get_block_datetime_utc(block),
                    )
                }
            },
        )


@dataclass
class GuildKickProposalAdded(Event):
    id: int
    memberAddress: bytes

    async def _handle(
        self, info: Info, block: BlockHeader, starknet_event: StarkNetEvent
    ):
        return await update_proposal(
            id=self.id,
            document=asdict(self),
            info=info,
            block=block,
            starknet_event=starknet_event,
        )


@dataclass
class WhitelistProposalAdded(Event):
    tokenName: str
    tokenAddress: bytes

    async def _handle(
        self, info: Info, block: BlockHeader, starknet_event: StarkNetEvent
    ):
        return await update_proposal(
            id=self.id,
            document=asdict(self),
            info=info,
            block=block,
            starknet_event=starknet_event,
        )


@dataclass
class UnWhitelistProposalAdded(Event):
    tokenName: str
    tokenAddress: bytes

    async def _handle(
        self, info: Info, block: BlockHeader, starknet_event: StarkNetEvent
    ):
        return await update_proposal(
            id=self.id,
            document=asdict(self),
            info=info,
            block=block,
            starknet_event=starknet_event,
        )


@dataclass
class SwapProposalAdded(Event):
    id: int
    tributeAddress: bytes
    tributeOffered: int
    paymentAddress: bytes
    paymentRequested: int

    async def _handle(
        self, info: Info, block: BlockHeader, starknet_event: StarkNetEvent
    ):
        return await update_proposal(
            id=self.id,
            document=asdict(self),
            info=info,
            block=block,
            starknet_event=starknet_event,
        )


# func VoteSubmitted(callerAddress: felt, proposalId: felt, vote: felt, onBehalfAddress: felt) {
@dataclass
class VoteSubmitted(Event):
    callerAddress: bytes
    proposalId: int
    vote: bool
    onBehalfAddress: bytes

    async def _handle(
        self, info: Info, block: BlockHeader, starknet_event: StarkNetEvent
    ):
        # TODO: store both calledAddress and onBehalfAddress, we'll need to know
        # who voted at some point
        if self.vote:
            update_proposal_vote = {"$push": {"yesVotes": self.onBehalfAddress}}
        else:
            update_proposal_vote = {"$push": {"noVotes": self.onBehalfAddress}}

        await info.storage.find_one_and_update(
            collection="proposals",
            filter={"id": self.proposalId},
            update=update_proposal_vote,
        )

        # TODO: add the proposalId to the member whenever we're indexing members

        return await super()._handle(info, block, starknet_event)


ALL_EVENTS: dict[str, Type[Event]] = {
    "ProposalAdded": ProposalAdded,
    "OnboardProposalAdded": OnboardProposalAdded,
    "ProposalStatusUpdated": ProposalStatusUpdated,
    "ProposalParamsUpdated": ProposalParamsUpdated,
    "SwapProposalAdded": SwapProposalAdded,
    "VoteSubmitted": VoteSubmitted,
}
