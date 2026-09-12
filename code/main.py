from loader import load_all


def main():
    data = load_all()

    print("financial_profiles:", len(data["financial_profiles"]))
    print("financial_events:", len(data["financial_events"]))
    print("exchange_rates:", len(data["exchange_rates"]))
    print("requests:", len(data["requests"]))
    print("sample_requests:", len(data["sample_requests"]))
    print("request_payment_options:", len(data["request_payment_options"]))
    print("messages:", len(data["messages"]))
    print("images:", len(data["images"]))
    print("output:", len(data["output"]))

    print("ALL DATASETS LOADED SUCCESSFULLY")


if __name__ == "__main__":
    main()