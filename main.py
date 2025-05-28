import json
import os
import bs4.element
import requests
import time
import progressbar
from collections import defaultdict

from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:60.0) Gecko/20100101 Firefox/60.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

# FlareSolverr configuration
FLARESOLVERR_URL = os.environ["proxy"]

def solve_cloudflare(url: str, retries: int = 3) -> str:
    """
    Use FlareSolverr to bypass Cloudflare protection and return HTML content
    """
    payload = {
        "cmd": "request.get",
        "url": url,
        "maxTimeout": 180000,
        "headers": HEADERS
    }
    
    for attempt in range(retries):
        try:
            response = requests.post(FLARESOLVERR_URL, json=payload, timeout=120)
            result = response.json()
            
            if result.get("status") == "ok":
                return result["solution"]["response"]
            else:
                print(f"FlareSolverr error for {url}: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"Attempt {attempt + 1} failed for {url}: {str(e)}")
            
        if attempt < retries - 1:
            time.sleep(5)  # Wait before retry
    
    # Fallback to regular requests if FlareSolverr fails
    print(f"FlareSolverr failed for {url}, trying regular request...")
    try:
        fallback_response = requests.get(url, headers=HEADERS, timeout=30)
        if fallback_response.status_code == 200:
            return fallback_response.content.decode('utf-8')
    except Exception as e:
        print(f"Fallback request also failed: {str(e)}")
    
    return ""

def get_page_content(url: str) -> str:
    """
    Get page content, using FlareSolverr if available, otherwise regular requests
    """
    # Check if we're running in GitHub Actions (FlareSolverr available)
    try:
        return solve_cloudflare(url)
        # Test if FlareSolverr is available
        # test_response = requests.get(FLARESOLVERR_URL, timeout=5)
        # if test_response.status_code == 200:
        #     print(f"Using FlareSolverr for {url}")
        #     return solve_cloudflare(url)
    except:
        pass
    
    # Fallback to regular requests
    print(f"Using regular requests for {url}")
    response = requests.get(url, headers=HEADERS, timeout=30)
    if response.status_code == 200:
        return response.content.decode('utf-8')
    return ""

def extract_item_data(href: str, info_block: bs4.Tag, name_to_info: dict) -> dict:
    item_url = "https://rustlabs.com" + href

    item_name = str(info_block.find_all(class_="r-cell")[0].getText())

    item_id = name_to_info.get(item_name, {}).get("id", "N/A")
    stack_size = name_to_info.get(item_name, {}).get("stack_size", "N/A")
    despawn_time = name_to_info.get(item_name, {}).get("despawn_time", "N/A")

    appending = {
        "name": info_block.find_all(class_="r-cell")[0].getText(),
        "image": "https://rustlabs.com" + info_block.find_all("img")[0]["src"],
        "id": item_id,
        "stack_size": stack_size,
        "despawn_time": despawn_time
    }

    try:
        # Use the new get_page_content function
        content = get_page_content(item_url)
        
        if not content:
            return appending

        bs = BeautifulSoup(content, "html.parser")
        td = bs.find_all(class_="stats-table")[0].find_all("td")
    except Exception as e:
        print(f"Error occurred while trying to scrape {item_url} for ID. Exception {e}")
        return appending

    if td != [] and len(td) >= 6:
        appending["id"] = td[1].getText()
        appending["stack_size"] = td[3].getText().replace("×", "")
        appending["despawn_time"] = td[5].getText().replace("min ", "mins").replace("hour ", "hour")

    return appending


def main() -> None:
    # Use FlareSolverr for the main page as well
    main_content = get_page_content('https://wiki.rustclash.com/group=itemlist')
    
    if not main_content:
        print("An Error Has Occurred with request")
        quit(1)

    output_json = defaultdict(list)
    output_markdown = "|Name|Image|ID|Stack Size|Despawn Time|\n|:-:|:-:|:-:|:-:|:-:|\n"

    soup = BeautifulSoup(main_content, 'html.parser')
    info_blocks = soup.find_all('div', class_='info-block group')

    current_heading = ""
    blocks = info_blocks[0].find_all(recursive=False)
    bar = progressbar.ProgressBar(maxval=len(blocks), widgets=[progressbar.Bar('=', '[', ']'), ' ',
                                                               progressbar.Percentage()])
    bar.start()

    name_to_info = {}
    try:
        previousfile = json.load(open("data/items.json", "r"))
        for item_type in previousfile:
            for item in previousfile[item_type]:
                name_to_info[item["name"]] = {"image": item["image"], "id": item["id"],
                                              "stack_size": item["stack_size"], "despawn_time": item["despawn_time"]}
    except:
        print("File does not exist or an error occurred.")

    for i, info_block in enumerate(blocks):
        if info_block.name == "h2":
            current_heading = info_block.getText()
        else:
            data = extract_item_data(info_block.get_attribute_list("href")[0], info_block, name_to_info)

            output_json[current_heading].append(data)
            output_markdown += f"|{data['name']}|![]({data['image']})|{data['id']}|{data['stack_size']}|" \
                               f"{data['despawn_time']}|\n"
            bar.update(i + 1)
            time.sleep(0.5)

    bar.finish()
    name_to_info_output = {}
    for item_type in output_json:
        for item in output_json[item_type]:
            name_to_info_output[item["name"]] = {"image": item["image"], "id": item["id"],
                                                 "stack_size": item["stack_size"], "despawn_time": item["despawn_time"]}

    # Ensure data directory exists
    import os
    os.makedirs("data", exist_ok=True)

    with open("data/items.md", "w") as md_out:
        md_out.write(output_markdown)

    with open("data/items.json", "w") as json_out:
        json_out.write(json.dumps(output_json, indent=3))

    with open("data/name_to_info.json", "w") as name_info_out:
        name_info_out.write(json.dumps(name_to_info_output, indent=3))


if __name__ == '__main__':
    main()
