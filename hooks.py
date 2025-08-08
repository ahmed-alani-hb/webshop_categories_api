app_name = "webshop_categories_api"
app_title = "Webshop Categories API"
app_publisher = "Your Company"
app_description = "Enhanced API endpoints for webshop categories with images"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "your.email@company.com"
app_license = "MIT"
app_version = "1.0.0"

# Dependencies
depends_on = ["webshop"]
required_apps = ["webshop"]

# Override webshop API methods and add new category methods
override_whitelisted_methods = {
	"webshop.webshop.api.get_product_filter_data": "webshop_categories_api.api.categories.get_product_filter_data_enhanced"
}