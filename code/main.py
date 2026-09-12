from loader import load_all
from normalizer import normalize_all


def main():
    data = load_all()
    data = normalize_all(data)

    print("financial_profiles:", len(data["financial_profiles"]))
    print("financial_events:", len(data["financial_events"]))
    print("exchange_rates:", len(data["exchange_rates"]))
    print("requests:", len(data["requests"]))
    print("sample_requests:", len(data["sample_requests"]))
    print(
        "request_payment_options:",
        len(data["request_payment_options"]),
    )
    print("messages:", len(data["messages"]))
    print("images:", len(data["images"]))
    print("output:", len(data["output"]))

    print()
    print("NORMALIZATION CHECK")

    print(
        "request_date type:",
        data["requests"]["request_date"].dtype,
    )

    print(
        "event_date type:",
        data["financial_events"]["event_date"].dtype,
    )

    print(
        "message sent_at type:",
        data["messages"]["sent_at"].dtype,
    )

    profile = data["financial_profiles"].iloc[0]

    print(
        "payment methods:",
        profile["payment_methods_user_will_consider_list"],
    )

    print()
    print("ALL DATASETS LOADED AND NORMALIZED SUCCESSFULLY")


if __name__ == "__main__":
    main()