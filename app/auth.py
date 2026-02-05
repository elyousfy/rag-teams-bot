"""
Azure AD authentication and authorization.

Validates that incoming requests are from authorized users
by checking their Azure AD group membership.
"""

import aiohttp
import structlog
from typing import Optional

from app import config

logger = structlog.get_logger()

# Microsoft Graph API endpoint
GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"


class AzureADAuth:
    """
    Handles Azure AD authentication and group membership validation.
    """

    def __init__(self):
        self._access_token: Optional[str] = None
        self._token_expires: float = 0

    async def _get_app_token(self) -> str:
        """
        Get an access token for the bot application using client credentials.
        """
        import time

        # Return cached token if still valid
        if self._access_token and time.time() < self._token_expires - 60:
            return self._access_token

        # Use tenant-specific endpoint for client credentials grant
        tenant_id = config.AZURE_TENANT_ID or "common"
        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

        data = {
            "grant_type": "client_credentials",
            "client_id": config.AZURE_APP_ID,
            "client_secret": config.AZURE_APP_SECRET,
            "scope": "https://graph.microsoft.com/.default",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(token_url, data=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error("Failed to get app token", status=response.status, error=error_text)
                    raise RuntimeError(f"Failed to get access token: {error_text}")

                token_data = await response.json()
                self._access_token = token_data["access_token"]
                self._token_expires = time.time() + token_data.get("expires_in", 3600)

                return self._access_token

    async def check_group_membership(self, user_id: str) -> bool:
        """
        Check if a user is a member of the allowed Azure AD group.

        Args:
            user_id: The Azure AD user object ID

        Returns:
            True if user is in the allowed group, False otherwise
        """
        if not config.ALLOWED_AD_GROUP_ID:
            # If no group configured, allow all authenticated users
            logger.warning("No ALLOWED_AD_GROUP_ID configured, allowing all users")
            return True

        try:
            token = await self._get_app_token()

            # Use the checkMemberGroups API
            url = f"{GRAPH_API_BASE}/users/{user_id}/checkMemberGroups"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            payload = {
                "groupIds": [config.ALLOWED_AD_GROUP_ID]
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        is_member = config.ALLOWED_AD_GROUP_ID in data.get("value", [])

                        logger.info(
                            "Group membership check",
                            user_id=user_id,
                            is_member=is_member,
                        )

                        return is_member
                    else:
                        error_text = await response.text()
                        logger.error(
                            "Group membership check failed",
                            user_id=user_id,
                            status=response.status,
                            error=error_text,
                        )
                        return False

        except Exception as e:
            logger.error("Error checking group membership", user_id=user_id, error=str(e))
            return False


# Global auth instance
_auth: Optional[AzureADAuth] = None


def get_auth() -> AzureADAuth:
    """Get the global auth instance."""
    global _auth
    if _auth is None:
        _auth = AzureADAuth()
    return _auth


async def is_user_authorized(user_aad_id: Optional[str]) -> bool:
    """
    Check if a user is authorized to use the bot.

    Args:
        user_aad_id: The user's Azure AD object ID

    Returns:
        True if authorized, False otherwise
    """
    if not user_aad_id:
        logger.warning("No user AAD ID provided")
        return False

    auth = get_auth()
    return await auth.check_group_membership(user_aad_id)
