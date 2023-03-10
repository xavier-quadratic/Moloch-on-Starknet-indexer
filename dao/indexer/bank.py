# pylint: disable=redefined-builtin
from dataclasses import asdict, dataclass

from apibara import Info
from apibara.model import BlockHeader, StarkNetEvent

from dao.indexer import storage
from dao.indexer.base_event import BaseEvent
from dao.utils import get_block_datetime_utc


@dataclass
class TokenWhitelisted(BaseEvent):
    tokenName: str
    tokenAddress: bytes

    async def _handle(
        self, info: Info, block: BlockHeader, starknet_event: StarkNetEvent
    ):
        token_dict = {
            **asdict(self),
            "whitelistedAt": get_block_datetime_utc(block),
        }
        await storage.update_bank(
            update={"$push": {"whitelistedTokens": token_dict}}, info=info
        )


@dataclass
class TokenUnWhitelisted(BaseEvent):
    tokenName: str
    tokenAddress: bytes

    async def _handle(
        self, info: Info, block: BlockHeader, starknet_event: StarkNetEvent
    ):
        token_dict = {
            **asdict(self),
            "unWhitelistedAt": get_block_datetime_utc(block),
        }
        await storage.update_bank(
            update={"$push": {"unWhitelistedTokens": token_dict}}, info=info
        )


@dataclass
class UserTokenBalanceIncreased(BaseEvent):
    memberAddress: bytes
    tokenAddress: bytes
    amount: int

    async def _handle(
        self, info: Info, block: BlockHeader, starknet_event: StarkNetEvent
    ):
        return await storage.update_balance(
            info=info,
            block=block,
            member_address=self.memberAddress,
            token_address=self.tokenAddress,
            amount=self.amount,
        )


@dataclass
class UserTokenBalanceDecreased(BaseEvent):
    memberAddress: bytes
    tokenAddress: bytes
    amount: int

    async def _handle(
        self, info: Info, block: BlockHeader, starknet_event: StarkNetEvent
    ):
        return await storage.update_balance(
            info=info,
            block=block,
            member_address=self.memberAddress,
            token_address=self.tokenAddress,
            amount=-self.amount,
        )
