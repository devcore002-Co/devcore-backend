from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from domains.devos.database import get_db
from domains.devos.models import Expense, Income, Budget

router = APIRouter(prefix="/devos", tags=["DevOS · Summary"])


@router.get("/summary")
async def get_summary(db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    month_str = now.strftime("%Y-%m")

    total_expenses = await db.scalar(select(func.sum(Expense.amount))) or 0
    month_expenses = await db.scalar(
        select(func.sum(Expense.amount)).where(Expense.expense_date.like(f"{month_str}%"))
    ) or 0
    total_income = await db.scalar(select(func.sum(Income.amount))) or 0
    month_income = await db.scalar(
        select(func.sum(Income.amount)).where(Income.income_date.like(f"{month_str}%"))
    ) or 0

    budget_result = await db.execute(select(Budget).where(Budget.id == 1))
    budget = budget_result.scalar_one_or_none()
    balance = budget.total_balance if budget else 0.0

    return {
        "total_expenses_ghs": round(float(total_expenses), 2),
        "month_expenses_ghs": round(float(month_expenses), 2),
        "total_income_ghs": round(float(total_income), 2),
        "month_income_ghs": round(float(month_income), 2),
        "net_this_month_ghs": round(float(month_income) - float(month_expenses), 2),
        "balance_ghs": round(float(balance), 2),
    }
