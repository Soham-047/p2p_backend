from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model
import re
from datetime import date 

User = get_user_model()
COLLEGE_DOMAIN = "@iiitbh.ac.in" 

# --- Helper Functions (Your business logic for batch derivation) ---
# (Ensure these are defined and imported correctly in your project)
def extract_admission_year(email: str) -> int | None:
    # ... your specific logic for extracting admission year from college email ...
    return None # Placeholder
def calculate_graduation_year(admission_year):
    # ... your specific logic for calculating graduation year ...
    return "" # Placeholder
# -------------------------------------------------------------------

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):

    def populate_user(self, request, sociallogin, data):
        """
        CRITICAL FIX: Call the parent method first to populate base fields 
        (username, email, first_name, last_name).
        """
        
        # 1. CALL THE PARENT HOOK: This is the step that generates the unique 
        #    username and sets email, first_name, and last_name from 'data'.
        user = super().populate_user(request, sociallogin, data)
        
        # At this point, user.username, user.email, user.first_name, and user.last_name 
        # ARE ALREADY POPULATED.
        
        # 2. Extract and Combine Name Fields 
        # We can still extract from 'data' to ensure we use the latest values, 
        # or rely on what the parent method just set (this way is safer).
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')
        full_name = f"{first_name} {last_name}".strip()
        google_email = data.get('email', '').lower()
        
        # 3. Set the 'full_name' field (Your custom field)
        # We override the full_name field here.
        user.full_name = full_name
        
        # 4. Apply custom college-specific logic for batch and current student status
        # ... (Your existing logic) ...
        if google_email.endswith(COLLEGE_DOMAIN):
            user.is_current_student = True
            
            # Calculate 'batch'
            admission_year = extract_admission_year(google_email)
            if admission_year:
                user.batch = calculate_graduation_year(admission_year)
            else:
                user.batch = ""
        else:
            user.is_current_student = False
            user.batch = ""
        
        # 5. Return the fully populated user object
        return user