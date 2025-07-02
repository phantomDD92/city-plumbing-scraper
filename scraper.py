from playwright.sync_api import sync_playwright
import os
import json
import requests

MAIN_URL = "https://www.cityplumbing.co.uk"

class CityPlumbingScraper():
    def __init__(self):
        self.categories = dict()
        self.products = dict()
        self.product_count = 0
        self._create_folder('results')
        pass

    def _has_product(self, skuCode):
        if os.path.exists(f"./results/{skuCode}.json"):
            return True
        return False
    
    def _save_product(self, product):
        self.product_count += 1
        print("+"*5, f"{self.product_count} : {product['skuCode']}")  
        with open(f"./results/{product['skuCode']}.json", 'w', encoding="utf-8") as f:
            json.dump(product, fp=f, indent='\t')

    def _save_images(self, sku, image_urls):
        images = []
        for i in range(len(image_urls)):
            filename = f"{sku}_{i}.jpg"
            if not os.path.exists(f"./results/{filename}"):
                resp = requests.get(image_urls[i])
                with open(f"./results/{filename}", 'wb') as f:
                    f.write(resp.content)
                print("++++++ ", filename)
            else:
                print("------ ", filename)
            images.append(filename)
        return images
    
    def _create_folder(self, path):
        try:
            if not os.path.exists(path):
                os.mkdir(path)
        except:
            pass

    def _goto_home(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.page.goto(MAIN_URL, timeout=100000, wait_until='domcontentloaded')
    
    def _close_address_popup(self):
        self.page.locator('div[data-test-id="delivery-address-popup"]').wait_for()
        self.page.locator("div[data-test-id='delivery-address-popup'] div[data-test-id='close-button']").first.click()

    def _close_cookies_dialog(self):
        self.page.locator("div#onetrust-button-group").wait_for()
        self.page.locator("div#onetrust-button-group button#onetrust-accept-btn-handler").first.click()

    def _get_top_categories(self):
        paths = []
        link_tags = self.page.locator('div[data-test-id="categories-menu-wrapper"] a[data-test-id="root-category-id"]').all()
        for link_tag in link_tags:
            link_str = str(link_tag.element_handle().get_attribute("href"))
            paths.append(link_str)
        return paths
    
    def _scrape_product(self, product_path):
        try:
            product = dict()
            self.page.goto(f"{MAIN_URL}{product_path}", wait_until="domcontentloaded", timeout=60000)
            # get category
            categories = []
            cat_tags = self.page.locator('div[data-test-id="breadcrumbs"] a').all()
            for cat_tag in cat_tags[1:]:
                categories.append(cat_tag.text_content())
            product["categories"] = categories
            # get skuCode
            skuCode = product_path.split("/")[-1]
            product["skuCode"] = skuCode
            # get product name
            name = self.page.locator('h1[data-test-id="product-name"]').first.text_content()
            product["name"] = name
            # get product price
            price_str = self.page.locator('h2[data-test-id="main-price"]').first.text_content()
            price = float(price_str[1:].replace(",", ""))
            product["salePrice"] = price
            # description
            desc_html = self.page.locator('div[data-test-id="product-overview"]').first.inner_html()
            product["description"] = "<div>" + desc_html + "</div>"
            # more info
            product["brand"] = ""
            spec = "<div><table>"
            data_tags = self.page.locator('div.ProductTechSpecification__Table-sc-1h7lq1c-0 > span').all()
            data_tags_len = len(data_tags)
            for i in range(0, data_tags_len -1, 2):
                key_str = data_tags[i].text_content()
                value_str = data_tags[i+1].text_content()
                spec += f'<tr><td><b>{key_str}</b></td><td>{value_str}</td></tr>'
                if "Brand" in key_str:
                    product["brand"] = value_str
            spec += "</table></div>"
            product["moreInfo"] = spec
            # image_urls
            image_urls = []
            image_tags_count = self.page.locator('div.styles__ListWrapper-sc-1x0wrbk-1 div.styles__ThumbnailWrapper-sc-1x0wrbk-3').count()
            if image_tags_count > 0:
                image_tags = self.page.locator('div.styles__ListWrapper-sc-1x0wrbk-1 div.styles__ThumbnailWrapper-sc-1x0wrbk-3').all()
                for image_tag in image_tags:
                    image_url = str(image_tag.get_attribute("id"))
                    image_url = "http:" + image_url.split("?")[0]
                    image_urls.append(image_url)
            else:
                image_tag = self.page.locator('div.styles__Image-sc-1q1tza3-2 img').first
                image_url = str(image_tag.get_attribute("src"))
                image_url = "http:" + image_url.split("?")[0]
                image_urls.append(image_url)
            product["images"] = self._save_images(skuCode, image_urls)
            self._save_product(product)
        except Exception as e:
            pass
            
    def _scrape_product_list(self, cat_path):
        paths = []
        page = 1
        while True:
            self.page.goto(f"{MAIN_URL}{cat_path}page-{page}", wait_until="domcontentloaded", timeout=60000)
            is_end = self.page.locator('div.fIluqC button[data-test-id="pag-button"]').count() == 0
            product_tags = self.page.locator('a[data-test-id="product-card-image"]').all()
            for product_tag in product_tags:
                product_path = str(product_tag.element_handle().get_attribute("href"))
                product_id = str(product_path).split("/")[-1]
                if product_id in self.products:
                    print("-"*5, product_id)    
                    continue
                self.products[product_id] = True
                if self._has_product(product_id):
                    self.product_count += 1
                    print("-"*5, f"{self.product_count} : {product_id}")    
                    continue
                
                paths.append(product_path)
            if is_end:
                break
            # break
            page += 1
        for path in paths:
            self._scrape_product(path)
            # break
    
    def _scrape_category(self, cat_path, depth=1):
        paths = []
        print("#"*depth, cat_path.split("/")[-2])
        self.page.goto(f"{MAIN_URL}{cat_path}", wait_until="domcontentloaded", timeout=60000)
        clp_wrapper_count = self.page.locator('div[data-test-id="clp-wrapper"]').count()
        if clp_wrapper_count > 0:
            # category list page
            category_tags = self.page.locator('div.CLPDesktop__CategoryListWrapper-sc-1h8ruv-11 div.styled__CategoryInner-sc-15zklas-2 > a').all()
            for category_tag in category_tags:
                category_path = str(category_tag.element_handle().get_attribute("href"))
                category_id = str(category_path).split("/")[-2]
                if category_id in self.categories:
                    print("*"*(depth+1), f"{category_id}")    
                    continue
                self.categories[category_id] = True
                paths.append(category_path)
            for path in paths:
                self._scrape_category(path, depth+1)
        else:
            # product list page
            self._scrape_product_list(cat_path)
        
    def start(self):
        self._goto_home()
        self._close_cookies_dialog()
        # self._close_address_popup()
        cat_paths = self._get_top_categories()
        # print(cat_paths)
        for cat_path in cat_paths:
            self._scrape_category(cat_path)
        self.page.wait_for_timeout(1000000)
        self.context.close()
        self.browser.close()

def main():
    scraper = CityPlumbingScraper()
    scraper.start()

if __name__ == "__main__":
    main()