"""Initialize canonical dataset schema templates for GramSetu AI.

Distinguishes schema/file readiness from authentic operational data availability.
Creates empty schema-compliant CSV headers without synthesizing, mocking, or fabricating
real operational records (prices, GPS coordinates, road segments, vehicle fleet).
"""

import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

DATASETS = {
    # Verified reference datasets
    "data/verified/commodity_master.csv": (
        "commodity_id,commodity_name,scientific_name,category,hsn_code,standard_moisture_max_pct,default_shelf_life_days,is_perishable\n"
    ),
    "data/verified/commodity_grades.csv": (
        "grade_id,commodity_id,grade_code,min_purity_pct,max_foreign_matter_pct,max_moisture_pct,description\n"
    ),
    "data/verified/administrative_locations.csv": (
        "location_id,lgd_code,location_name,location_type,district_name,state_code,pincode,latitude,longitude\n"
    ),
    "data/verified/mandi_master.csv": (
        "market_id,market_name,apmc_code,state_code,district_name,latitude,longitude,is_enam_integrated\n"
    ),
    "data/verified/daily_mandi_prices.csv": (
        "observation_id,market_id,commodity_id,variety,grade,price_date,min_price_paise_per_gram,max_price_paise_per_gram,modal_price_paise_per_gram,original_reported_unit,raw_modal_price_rs_per_quintal,source_url\n"
    ),
    "data/verified/daily_mandi_arrivals.csv": (
        "arrival_id,market_id,commodity_id,arrival_date,arrival_quantity_grams,original_reported_quantity_tonnes\n"
    ),
    "data/verified/road_nodes.csv": (
        "node_id,name,lat,lon,node_type\n"
    ),
    "data/verified/road_segments.csv": (
        "edge_id,source_node,target_node,distance_meters,speed_kmh,road_class,weight_limit_grams,is_open,closure_reason\n"
    ),
    "data/verified/storage_facilities.csv": (
        "facility_id,facility_name,fpo_id,facility_type,total_capacity_grams,temperature_controlled,latitude,longitude\n"
    ),
    "data/verified/crop_shelf_life_rules.csv": (
        "rule_id,crop_name,ambient_shelf_life_days,cold_storage_shelf_life_days,optimal_storage_temp_c,optimal_humidity_pct\n"
    ),
    "data/verified/freight_rate_cards.csv": (
        "rate_card_id,vehicle_type,base_mobilization_paise,per_km_paise,max_capacity_grams\n"
    ),
    "data/verified/settlement_deductions.csv": (
        "deduction_code,deduction_name,deduction_type,statutory_authority,rate_basis,default_rate_paise_or_pct\n"
    ),

    # Operator confirmed registries
    "data/operator_confirmed/fpo_master.csv": (
        "fpo_id,fpo_name,cin_registration_no,head_office_location_id,operating_district,member_farmer_count\n"
    ),
    "data/operator_confirmed/farmer_registry.csv": (
        "farmer_id,farmer_name,fpo_id,village_location_id,landholding_acres,primary_crop,kyc_verified\n"
    ),
    "data/operator_confirmed/buyer_registry.csv": (
        "buyer_id,business_name,gstin,buyer_category,terminal_location_id,credit_rating\n"
    ),
    "data/operator_confirmed/vehicle_fleet.csv": (
        "vehicle_id,fpo_id,driver_id,capacity_grams,vehicle_type,is_available,created_at\n"
    ),

    # Derived summary outputs
    "data/derived/demand_gap_summary.csv": (
        "summary_id,crop,grade,demanded_grams,supplied_grams,gap_grams,status\n"
    ),
    "data/derived/route_evaluations.csv": (
        "evaluation_id,origin_node,destination_node,distance_meters,estimated_duration_minutes,is_viable\n"
    ),

    # Synthetic test datasets
    "data/synthetic_test/test_buyer_requirements.csv": (
        "requirement_id,buyer_id,crop,variety,grade,needed_grams,allocated_grams,delivery_window_start,delivery_window_end,max_price_paise_per_gram,status,created_at\n"
    ),
    "data/synthetic_test/test_harvest_forecasts.csv": (
        "forecast_id,farmer_id,fpo_id,crop,variety,grade,estimated_grams,harvest_start_date,harvest_end_date,confidence_score,created_at,status\n"
    ),
    "data/synthetic_test/test_inventory_lots.csv": (
        "lot_id,fpo_id,farmer_id,crop,variety,grade,quantity_grams,reserved_grams,available_grams,storage_location,custody,version,created_at,status\n"
    ),
}


def main():
    created = 0
    for rel_path, header in DATASETS.items():
        abs_path = os.path.join(REPO_ROOT, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        if not os.path.exists(abs_path):
            with open(abs_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(header)
            created += 1
            print(f"Created template: {rel_path}")
        else:
            print(f"Already exists: {rel_path}")
    print(f"Done. Initialized {created} schema templates.")


if __name__ == "__main__":
    main()
