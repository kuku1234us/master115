import requests

def main():
    """Fetches and prints the TRX and USDT balance for a given Tron address."""
    address = "TSeVWaLuqZyg39YfcmxLPa3G3nDsDX2HkQ"
    api_url = f"https://api.trongrid.io/v1/accounts/{address}"
    
    try:
        response = requests.get(api_url)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        data = response.json()

        if not data.get("data") or not data["data"]:
             print(f"Error: No data found for address {address}")
             return

        account_data = data["data"][0]
        
        # TRX Balance (check if 'balance' key exists)
        trx_balance = int(account_data.get("balance", 0)) / 1_000_000
        
        # USDT Balance (check if 'trc20' and the specific token ID exist)
        usdt_balance = 0
        if "trc20" in account_data:
             # Find USDT token by its contract address
             usdt_token_id = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
             for token_info in account_data["trc20"]:
                  if usdt_token_id in token_info:
                       usdt_balance = int(token_info[usdt_token_id]) / 1_000_000
                       break # Found it, no need to check further

        print(f"Address: {address}")
        print(f"TRX: {trx_balance}")
        print(f"USDT (TRC20): {usdt_balance}")

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from TronGrid: {e}")
    except KeyError as e:
        print(f"Error parsing response data (missing key): {e}")
        # Optionally print the raw data for debugging
        # print("Raw data:", data)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()