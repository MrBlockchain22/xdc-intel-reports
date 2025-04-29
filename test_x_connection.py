import tweepy

# Load credentials
API_KEY = 'zxItFW1ex80dMwHgasu0wcmi0'
API_SECRET = 'bX3kLHdh6OmV3dHS6LgfgieOdVlbfTrvTvPDYPp5k6wAUkra3V'
ACCESS_TOKEN = '70089191-mPXkqngcvrh0pkrsxW1rISPXfFe748gyFQi80VS4e'
ACCESS_TOKEN_SECRET = 'sEi0fanDNBNcfrBo0XMQMSsGIIcgRcSciASG4vkkNbljo'

# Authenticate
auth = tweepy.OAuth1UserHandler(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
api = tweepy.API(auth)

try:
    user = api.verify_credentials()
    if user:
        print(f"[+] Authentication successful! Logged in as: @{user.screen_name}")
    else:
        print("[-] Authentication failed. Please check credentials.")
except Exception as e:
    print(f"[-] Error during authentication: {e}")
