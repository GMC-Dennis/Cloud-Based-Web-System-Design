from app.modules.scoring.infrastructure.scoring_engine import MerchantFeatures


def test_bucketed_rounds_to_nearest_bucket_width():
    features = MerchantFeatures(sales_velocity=2023.0, receivables_days=4.6, chama_punctuality=87.0, margin_stability=0.231)
    bucketed = features.bucketed()
    assert bucketed["sales_velocity"] == 2000.0  # nearest 50
    assert bucketed["receivables_days"] == 5.0  # nearest 1
    assert bucketed["chama_punctuality"] == 85.0  # nearest 5
    assert bucketed["margin_stability"] == 0.24  # nearest 0.02, rounds up from .231->.23? check below


def test_bucketed_collapses_nearby_values_to_same_key():
    a = MerchantFeatures(sales_velocity=2001.0, receivables_days=5.0, chama_punctuality=90.0, margin_stability=0.25)
    b = MerchantFeatures(sales_velocity=2024.0, receivables_days=5.0, chama_punctuality=90.0, margin_stability=0.25)
    assert a.bucketed() == b.bucketed()


def test_bucketed_separates_values_across_bucket_boundary():
    a = MerchantFeatures(sales_velocity=2000.0, receivables_days=5.0, chama_punctuality=90.0, margin_stability=0.25)
    b = MerchantFeatures(sales_velocity=2100.0, receivables_days=5.0, chama_punctuality=90.0, margin_stability=0.25)
    assert a.bucketed() != b.bucketed()


def test_feature_bounds_are_validated():
    import pytest

    with pytest.raises(ValueError):
        MerchantFeatures(sales_velocity=-1, receivables_days=0, chama_punctuality=0, margin_stability=0)
    with pytest.raises(ValueError):
        MerchantFeatures(sales_velocity=0, receivables_days=0, chama_punctuality=101, margin_stability=0)
