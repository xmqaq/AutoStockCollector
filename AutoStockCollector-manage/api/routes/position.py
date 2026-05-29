"""
持仓管理API路由
"""
from fastapi import APIRouter, HTTPException
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/api/position", tags=["持仓管理"])


class PositionCreate(BaseModel):
    code: str
    shares: int
    avg_cost: float
    stop_loss: Optional[float] = 0
    target_price: Optional[float] = 0


class PositionUpdate(BaseModel):
    shares: Optional[int] = None
    avg_cost: Optional[float] = None
    stop_loss: Optional[float] = None
    target_price: Optional[float] = None


@router.get("/list")
async def list_positions():
    from modules.position import position_manager
    positions = position_manager.list_positions()
    return {"code": 200, "data": positions, "message": "success"}


@router.get("/portfolio")
async def get_portfolio():
    from modules.position import position_manager
    portfolio = position_manager.calculate_portfolio()
    return {"code": 200, "data": portfolio, "message": "success"}


@router.get("/distribution")
async def get_distribution():
    from modules.position import position_manager
    distribution = position_manager.get_distribution()
    return {"code": 200, "data": distribution, "message": "success"}


@router.get("/alerts")
async def get_alerts():
    from modules.position import alert_system
    alerts = alert_system.check_alerts()
    return {"code": 200, "data": alerts, "message": "success"}


@router.post("/save")
async def save_position(data: PositionCreate):
    from modules.position import position_manager
    try:
        result = position_manager.add_position(
            code=data.code,
            shares=data.shares,
            avg_cost=data.avg_cost,
            stop_loss=data.stop_loss or 0,
            target_price=data.target_price or 0
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return {"code": 200, "data": result, "message": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/update/{code}")
async def update_position(code: str, data: PositionUpdate):
    from modules.position import position_manager
    try:
        result = position_manager.update_position(
            code=code,
            shares=data.shares,
            avg_cost=data.avg_cost,
            stop_loss=data.stop_loss,
            target_price=data.target_price
        )
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return {"code": 200, "data": result, "message": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete")
async def delete_position(code: str):
    from modules.position import position_manager
    try:
        success = position_manager.remove_position(code)
        if not success:
            raise HTTPException(status_code=404, detail="Position not found")
        return {"code": 200, "message": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch_save")
async def batch_save_positions(positions: List[PositionCreate]):
    from modules.position import position_manager
    results = []
    for p in positions:
        try:
            result = position_manager.add_position(
                code=p.code,
                shares=p.shares,
                avg_cost=p.avg_cost,
                stop_loss=p.stop_loss or 0,
                target_price=p.target_price or 0
            )
            if "error" not in result:
                results.append(result)
        except Exception as e:
            logger.error(f"Batch save failed for {p.code}: {e}")

    return {"code": 200, "data": results, "message": f"Saved {len(results)} positions"}
