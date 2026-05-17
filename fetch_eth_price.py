import requests

def fetch_eth_price():
    url = "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        price = data['ethereum']['usd']
        
        with open('eth_price.txt', 'w') as f:
            f.write(str(price))
            
        print(f"Successfully saved Ethereum price: ${price} to eth_price.txt")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    fetch_eth_price()
