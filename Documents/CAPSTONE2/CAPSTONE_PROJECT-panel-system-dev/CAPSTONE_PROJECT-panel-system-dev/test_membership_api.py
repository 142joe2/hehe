#!/usr/bin/env python
"""Test the membership registration API endpoint."""
import requests
import json
from bs4 import BeautifulSoup

# Test data for membership registration
test_data = {
    "first_name": "John",
    "middle_initial": "Q",
    "last_name": "Doe",
    "username": "johndoe",
    "email": "john@example.com",
    "department": "Engineering",
    "position": "Software Engineer",
    "membership_category": "Permanent",
    "payment_method": "Bank Transfer",
    "amount": "100.00",
    "payment_date": "2026-07-23",
    "password": "TestPass123!",
    "confirm_password": "TestPass123!",
}

url = "http://127.0.0.1:8000/api/public/membership-registration/"
form_url = "http://127.0.0.1:8000/register/"

try:
    session = requests.Session()
    
    # Fetch the form page to get CSRF token
    print("Fetching CSRF token...")
    form_response = session.get(form_url)
    
    if form_response.status_code == 200:
        soup = BeautifulSoup(form_response.text, 'html.parser')
        csrf_input = soup.find('input', {'name': 'csrfmiddlewaretoken'})
        if csrf_input:
            csrf_token = csrf_input.get('value')
            print(f"CSRF Token obtained: {csrf_token[:10]}...")
            test_data['csrfmiddlewaretoken'] = csrf_token
        else:
            print("Warning: CSRF token not found in form, trying without it...")
    
    # Now post the data with the session (which has cookies)
    response = session.post(url, data=test_data)
    print(f"\nStatus Code: {response.status_code}")
    
    # Check if it's a JSON response
    try:
        json_response = response.json()
        print(f"JSON Response: {json.dumps(json_response, indent=2)}")
    except:
        print(f"Text Response: {response.text[:500]}")
    
    if response.status_code == 201:
        print("\n✓ API endpoint is working! Request succeeded.")
    elif response.status_code == 200:
        print("\n✓ API endpoint responded! (200 OK)")
    else:
        print(f"\n✗ API returned status {response.status_code}")
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
