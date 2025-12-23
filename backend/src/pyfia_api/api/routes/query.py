"""Direct query endpoints for FIA data."""

from fastapi import APIRouter, HTTPException

from ...auth import require_auth
from ...models.schemas import (
    AreaQuery,
    AreaResponse,
    VolumeQuery,
    VolumeResponse,
    BiomassQuery,
    BiomassResponse,
    TPAQuery,
    CompareQuery,
    CompareResponse,
)
from ...services.fia_service import fia_service

# All query endpoints require authentication
router = APIRouter(dependencies=[require_auth])


@router.post("/area", response_model=AreaResponse)
async def query_area(query: AreaQuery):
    """Query forest land area for specified states."""
    try:
        result = await fia_service.query_area(
            states=query.states,
            land_type=query.land_type,
            grp_by=query.grp_by,
        )
        return AreaResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/volume", response_model=VolumeResponse)
async def query_volume(query: VolumeQuery):
    """Query timber volume for specified states."""
    try:
        result = await fia_service.query_volume(
            states=query.states,
            by_species=query.by_species,
            tree_domain=query.tree_domain,
        )
        return VolumeResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/biomass", response_model=BiomassResponse)
async def query_biomass(query: BiomassQuery):
    """Query biomass and carbon for specified states."""
    try:
        result = await fia_service.query_biomass(
            states=query.states,
            land_type=query.land_type,
            by_species=query.by_species,
        )
        return BiomassResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tpa")
async def query_tpa(query: TPAQuery):
    """Query trees per acre for specified states."""
    try:
        result = await fia_service.query_tpa(
            states=query.states,
            tree_domain=query.tree_domain,
            by_species=query.by_species,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare", response_model=CompareResponse)
async def compare_states(query: CompareQuery):
    """Compare a metric across multiple states."""
    try:
        result = await fia_service.compare_states(
            states=query.states,
            metric=query.metric,
            land_type=query.land_type,
        )
        return CompareResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/states")
async def list_states():
    """List available states."""
    states = [
        {"code": "AL", "name": "Alabama"},
        {"code": "AK", "name": "Alaska"},
        {"code": "AZ", "name": "Arizona"},
        {"code": "AR", "name": "Arkansas"},
        {"code": "CA", "name": "California"},
        {"code": "CO", "name": "Colorado"},
        {"code": "CT", "name": "Connecticut"},
        {"code": "DE", "name": "Delaware"},
        {"code": "FL", "name": "Florida"},
        {"code": "GA", "name": "Georgia"},
        {"code": "HI", "name": "Hawaii"},
        {"code": "ID", "name": "Idaho"},
        {"code": "IL", "name": "Illinois"},
        {"code": "IN", "name": "Indiana"},
        {"code": "IA", "name": "Iowa"},
        {"code": "KS", "name": "Kansas"},
        {"code": "KY", "name": "Kentucky"},
        {"code": "LA", "name": "Louisiana"},
        {"code": "ME", "name": "Maine"},
        {"code": "MD", "name": "Maryland"},
        {"code": "MA", "name": "Massachusetts"},
        {"code": "MI", "name": "Michigan"},
        {"code": "MN", "name": "Minnesota"},
        {"code": "MS", "name": "Mississippi"},
        {"code": "MO", "name": "Missouri"},
        {"code": "MT", "name": "Montana"},
        {"code": "NE", "name": "Nebraska"},
        {"code": "NV", "name": "Nevada"},
        {"code": "NH", "name": "New Hampshire"},
        {"code": "NJ", "name": "New Jersey"},
        {"code": "NM", "name": "New Mexico"},
        {"code": "NY", "name": "New York"},
        {"code": "NC", "name": "North Carolina"},
        {"code": "ND", "name": "North Dakota"},
        {"code": "OH", "name": "Ohio"},
        {"code": "OK", "name": "Oklahoma"},
        {"code": "OR", "name": "Oregon"},
        {"code": "PA", "name": "Pennsylvania"},
        {"code": "RI", "name": "Rhode Island"},
        {"code": "SC", "name": "South Carolina"},
        {"code": "SD", "name": "South Dakota"},
        {"code": "TN", "name": "Tennessee"},
        {"code": "TX", "name": "Texas"},
        {"code": "UT", "name": "Utah"},
        {"code": "VT", "name": "Vermont"},
        {"code": "VA", "name": "Virginia"},
        {"code": "WA", "name": "Washington"},
        {"code": "WV", "name": "West Virginia"},
        {"code": "WI", "name": "Wisconsin"},
        {"code": "WY", "name": "Wyoming"},
    ]
    return {"states": states}


@router.get("/metrics")
async def list_metrics():
    """List available metrics for queries."""
    return {
        "metrics": [
            {
                "name": "area",
                "description": "Forest land area in acres",
                "eval_type": "EXPALL",
            },
            {
                "name": "volume",
                "description": "Timber volume in cubic feet",
                "eval_type": "EXPVOL",
            },
            {
                "name": "biomass",
                "description": "Tree biomass in short tons",
                "eval_type": "EXPVOL",
            },
            {
                "name": "tpa",
                "description": "Trees per acre",
                "eval_type": "EXPVOL",
            },
            {
                "name": "mortality",
                "description": "Annual tree mortality",
                "eval_type": "EXPMORT",
            },
            {
                "name": "growth",
                "description": "Net annual growth in cubic feet",
                "eval_type": "EXPGROW",
            },
        ]
    }
