from __future__ import annotations

import dataclasses
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.main.python.api.dependencies import get_db, get_account_repo, get_trade_repo, require_account
from src.main.python.api.schemas.account import AccountCreate, AccountResponse, AccountUpdate
from src.main.python.models.account import Account
from src.main.python.models.enums import Platform
from src.main.python.services.account_repository import AccountRepository
from src.main.python.services.trade_repository import TradeRepository

router = APIRouter(prefix="/accounts", tags=["accounts"])


def _build_response(account: Account, trade_count: int = None) -> AccountResponse:
    return AccountResponse(
        account_id=account.account_id,
        broker=account.broker,
        platform=account.platform,
        prop_firm=account.prop_firm,
        challenge_phase=account.challenge_phase,
        starting_balance=account.starting_balance,
        account_currency=account.account_currency,
        created_at=account.created_at,
        trade_count=trade_count,
    )


@router.get("", response_model=List[AccountResponse])
def list_accounts(
    db: Session = Depends(get_db),
):
    account_repo = get_account_repo(db)
    trade_repo = get_trade_repo(db)
    accounts = account_repo.list_all()
    return [
        _build_response(acc, trade_count=trade_repo.count(acc.account_id))
        for acc in accounts
    ]


@router.post("", response_model=AccountResponse, status_code=201)
def create_account(
    body: AccountCreate,
    db: Session = Depends(get_db),
):
    account_repo = get_account_repo(db)
    account = Account(
        account_id=body.account_id,
        broker=body.broker,
        platform=body.platform,
        prop_firm=body.prop_firm,
        challenge_phase=body.challenge_phase,
        starting_balance=body.starting_balance,
        account_currency=body.account_currency,
    )
    saved = account_repo.save(account)
    return _build_response(saved)


@router.get("/{account_id}", response_model=AccountResponse)
def get_account(
    account_id: str,
    db: Session = Depends(get_db),
):
    account_repo = get_account_repo(db)
    account = require_account(account_id, account_repo)
    return _build_response(account)


@router.patch("/{account_id}", response_model=AccountResponse)
def update_account(
    account_id: str,
    body: AccountUpdate,
    db: Session = Depends(get_db),
):
    account_repo = get_account_repo(db)
    existing = require_account(account_id, account_repo)
    update_data = body.model_dump(exclude_none=True)
    updated = dataclasses.replace(existing, **update_data)
    saved = account_repo.save(updated)
    return _build_response(saved)


@router.delete("/{account_id}")
def delete_account(
    account_id: str,
    db: Session = Depends(get_db),
):
    account_repo = get_account_repo(db)
    require_account(account_id, account_repo)
    account_repo.delete(account_id)
    return {"deleted": True}
