"""Test county-level queries to verify plot_domain filtering works."""

import asyncio
import os
import sys

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from askfia_api.services.fia_service import FIAService


async def test_county_query():
    """Test that county queries return county-specific data, not statewide."""
    service = FIAService()

    print("=" * 60)
    print("Testing County-Level Query (Wake County, NC)")
    print("=" * 60)

    # Test 1: Get statewide area for comparison
    print("\n1. Querying NC statewide forest area...")
    try:
        statewide = await service.query_area(["NC"], land_type="forest")
        statewide_total = statewide.get("total", 0)
        print(f"   NC Statewide: {statewide_total:,.0f} acres")
    except Exception as e:
        print(f"   ERROR: {e}")
        statewide_total = 0

    # Test 2: Get Wake County area (FIPS 183)
    print("\n2. Querying Wake County (FIPS 183) forest area...")
    try:
        county = await service.query_by_county(
            state="NC",
            county_fips=183,
            metric="area",
            land_type="forest"
        )
        print(f"   Result: {county}")

        if "error" in county:
            print(f"   ERROR: {county['error']}")
            county_total = 0
        else:
            county_total = county.get("total_area_acres", 0)
            print(f"   Wake County: {county_total:,.0f} acres")
    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()
        county_total = 0

    # Test 3: Verify county is much smaller than state
    print("\n3. Verification...")
    if statewide_total > 0 and county_total > 0:
        ratio = county_total / statewide_total * 100
        print(f"   County/State ratio: {ratio:.2f}%")

        if ratio > 50:
            print("   FAIL: County total is too close to statewide total!")
            print("   This suggests plot_domain filtering is NOT working.")
        elif ratio < 0.1:
            print("   WARNING: County total seems very small. Check FIPS code.")
        else:
            print("   PASS: County total is reasonably smaller than statewide.")
    else:
        print("   SKIP: Cannot verify - missing data")

    # Test 4: Direct pyFIA test with plot_domain
    print("\n4. Testing pyFIA plot_domain directly...")
    try:
        from pyfia import area
        import inspect

        # Check if plot_domain parameter exists
        sig = inspect.signature(area)
        params = list(sig.parameters.keys())
        print(f"   area() parameters: {params}")

        if "plot_domain" in params:
            print("   plot_domain parameter EXISTS in pyFIA")
        else:
            print("   plot_domain parameter MISSING - pyFIA version issue!")

    except Exception as e:
        print(f"   ERROR: {e}")

    # Test 5: Test with actual database connection
    print("\n5. Testing direct database query with plot_domain...")
    try:
        with service._get_fia_connection("NC") as db:
            # Test without filter
            result_all = db.area(land_type="forest")
            total_all = result_all["ESTIMATE"].sum() if "ESTIMATE" in result_all.columns else 0
            print(f"   Without filter: {total_all:,.0f} acres")

            # Test with plot_domain
            result_county = db.area(land_type="forest", plot_domain="COUNTYCD == 183")
            total_county = result_county["ESTIMATE"].sum() if "ESTIMATE" in result_county.columns else 0
            print(f"   With plot_domain: {total_county:,.0f} acres")

            if total_county == total_all:
                print("   FAIL: plot_domain filter had no effect!")
            elif total_county < total_all:
                print("   PASS: plot_domain reduced the total as expected")

    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("Test complete")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_county_query())
