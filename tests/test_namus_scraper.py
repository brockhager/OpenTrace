import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from scrapers.namus_scraper import NamUsScraper


@pytest.mark.asyncio
async def test_scrape_case_success():
    """Test successful scraping of a NamUs case."""
    mock_html = """
    <html>
    <head><title>Case MP12345</title></head>
    <body>
        <h1 class="case-name">John Doe</h1>
        <table>
            <tr><td>Age:</td><td>25</td></tr>
            <tr><td>Sex:</td><td>Male</td></tr>
        </table>
        <div>
            <h2>Circumstances of Disappearance</h2>
            <p>Last seen in New York City</p>
        </div>
        <img class="case-photo" src="/images/photo1.jpg" />
    </body>
    </html>
    """

    with patch('httpx.AsyncClient.get') as mock_get:
        mock_response = AsyncMock()
        mock_response.text = mock_html
        mock_response.raise_for_status = AsyncMock()
        mock_get.return_value = mock_response

        async with NamUsScraper() as scraper:
            result = await scraper.scrape_case("MP12345")

        assert result is not None
        assert result['pfif_id'] == 'opentrace.org/person.namus.MP12345'
        assert result['full_name'] == 'John Doe'
        assert result['age'] == 25
        assert result['sex'] == 'Male'
        assert 'New York City' in result['last_seen_location']
        assert 'photo_urls' in result


@pytest.mark.asyncio
async def test_scrape_case_no_data():
    """Test scraping a case with no extractable data."""
    mock_html = """
    <html>
    <body>
        <p>No case information available</p>
    </body>
    </html>
    """

    with patch('httpx.AsyncClient.get') as mock_get:
        mock_response = AsyncMock()
        mock_response.text = mock_html
        mock_response.raise_for_status = AsyncMock()
        mock_get.return_value = mock_response

        async with NamUsScraper() as scraper:
            result = await scraper.scrape_case("MP99999")

        assert result is None


@pytest.mark.asyncio
async def test_scrape_case_http_error():
    """Test handling of HTTP errors."""
    with patch('httpx.AsyncClient.get') as mock_get:
        mock_get.side_effect = Exception("HTTP 404")

        async with NamUsScraper() as scraper:
            result = await scraper.scrape_case("MP00000")

        assert result is None


@pytest.mark.asyncio
async def test_cache_validation():
    """Test that caching works and hash is computed."""
    mock_html = "<html><body>Test</body></html>"

    with patch('httpx.AsyncClient.get') as mock_get:
        mock_response = AsyncMock()
        mock_response.text = mock_html
        mock_response.raise_for_status = AsyncMock()
        mock_get.return_value = mock_response

        async with NamUsScraper() as scraper:
            result1 = await scraper.scrape_case("MP11111")
            # Second call should use cache
            result2 = await scraper.scrape_case("MP11111")

        assert result1 == result2
        # Verify cache file exists
        cache_path = scraper._get_cache_path("MP11111")
        assert cache_path.exists()


if __name__ == "__main__":
    asyncio.run(pytest.main([__file__, "-v"]))