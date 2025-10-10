import json
import copy
import os

class OpenAPIDocumentation:
    def __init__(self, filepath):
        """Initialize and load the OpenAPI spec."""
        if not os.path.exists(filepath):
            raise FileNotFoundError("File not found")

        base_name, ext = os.path.splitext(filepath)
        restructured_path = f"{base_name}_restructured{ext}"

        if not os.path.exists(restructured_path):
            self.transform_file(filepath, restructured_path)

        with open(restructured_path, 'r', encoding='utf-8') as f:
            self.openapi_spec = json.load(f)

    def transform_file(self, input_path, output_path):
        with open(input_path, "r") as file:
            swagger_data = json.load(file)

        swagger_data = self.dereference_all(swagger_data)
        swagger_data["paths"] = self.restructure_paths(swagger_data["paths"])

        with open(output_path, "w") as file:
            json.dump(swagger_data, file, indent=4)

    def resolve_ref(self, obj, root, seen=None):
        if seen is None:
            seen = set()

        if isinstance(obj, dict):
            if "$ref" in obj:
                ref = obj["$ref"]
                if ref.startswith("#/"):
                    path = ref.lstrip("#/").split("/")
                    ref_obj = root
                    for part in path:
                        ref_obj = ref_obj.get(part)
                        if ref_obj is None:
                            return obj
                    
                    ref_key = "/".join(path)
                    if ref_key in seen:
                        return obj
                    
                    seen.add(ref_key)
                    return self.resolve_ref(copy.deepcopy(ref_obj), root, seen)
                else:
                    return obj
            else:
                return {k: self.resolve_ref(v, root, seen) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.resolve_ref(i, root, seen) for i in obj]
        else:
            return obj

    def dereference_all(self, openapi):
        # Dereference path parameters and responses
        for path, path_item in openapi.get("paths", {}).items():
            for method, operation in path_item.items():
                if not isinstance(operation, dict):
                    continue
                if "parameters" in operation:
                    operation["parameters"] = [
                        self.resolve_ref(param, openapi) for param in operation["parameters"]
                    ]
                if "responses" in operation:
                    for code, response in operation["responses"].items():
                        operation["responses"][code] = self.resolve_ref(response, openapi)
                    
                # Request body (OpenAPI 3.0)
                if "requestBody" in operation:
                    operation["requestBody"] = self.resolve_ref(operation["requestBody"], openapi)

        # Dereference schemas (OpenAPI 3)
        if "components" in openapi and "schemas" in openapi["components"]:
            for name, schema in openapi["components"]["schemas"].items():
                openapi["components"]["schemas"][name] = self.resolve_ref(schema, openapi)

        # Dereference definitions (OpenAPI 2)
        if "definitions" in openapi:
            for name, schema in openapi["definitions"].items():
                openapi["definitions"][name] = self.resolve_ref(schema, openapi)

        return openapi

    def restructure_paths(self, paths):
        transformed_paths = []
        for endpoint, methods in paths.items():
            endpoint_node = {
                "endpoint": endpoint,
                "parameters": methods.get("parameters", []),
                "methods": {}
            }

            for method, details in methods.items():
                if method in ["get", "post", "put", "delete", "patch"]:
                    method_details = {
                        "operationId": details.get("operationId"),
                        "method_description": details.get("summary") or details.get("description") or "",
                        "parameters": details.get("parameters", []),
                        "responses": [],
                        "tags": details.get("tags", [])
                    }

                    # If OpenAPI 3 requestBody exists, convert to 'in: body' style param
                    if "requestBody" in details:
                        content = details["requestBody"].get("content", {})
                        for media_type, media_obj in content.items():
                            method_details["parameters"].append({
                                "name": "body",
                                "in": "body",
                                "schema": media_obj.get("schema", {}),
                                "examples": media_obj.get("examples", {})
                            })
                            break  # Only first media type
                    else:
                        # OpenAPI 2: copy all parameters
                        method_details["parameters"] = [
                            param for param in details.get("parameters", [])
                        ]

                    # Responses (support both OAS2 and OAS3)
                    for status_code, response in details.get("responses", {}).items():
                        response_node = {
                            "status_code": str(status_code),
                            "response_description": response.get("description", ""),
                            "content": {}
                        }

                        if "content" in response:  # OpenAPI 3
                            for media_type, media_obj in response["content"].items():
                                response_node["content"] = {
                                    "schema": media_obj.get("schema", {}),
                                    "examples": media_obj.get("examples", {})
                                }
                                break

                        else:  # OpenAPI 2
                            response_node["content"] = {
                                "schema": response.get("schema", {}),
                                "examples": response.get("examples", {})
                            }

                        method_details["responses"].append(response_node)

                    endpoint_node["methods"][method.upper()] = method_details

            transformed_paths.append(endpoint_node)

        return transformed_paths

    def get_documentation(self, filters: dict = None):
        """
        Get filtered documentation. Filters is a dictionary with optional keys:
        "endpoint", "method", "parameters", "tags", "operationId", "method_description", "responses"

        - If any value is None, it won't be filtered by that key.
        - If the key isn't present in the dictionary, it won't be included in the output.
        - If no filters are provided, only endpoint names are shown (no methods).
        - Methods are only shown if any key other than "endpoint" is present, or if "method" is present.
        """
        filters = filters or {}
        show_methods = any(k for k in filters if k != "endpoint") or "method" in filters

        # Normalize filter values to lists (or None)
        def normalize(value):
            if value is None:
                return None
            if isinstance(value, str):
                return [value]
            return value

        filters = {k: normalize(v) for k, v in filters.items()}

        results = []

        for i, endpoint in enumerate(self.openapi_spec.get("paths", [])):
            ep_name = endpoint.get("endpoint", "")

            # Filter by endpoint string
            if filters.get("endpoint") and not any(f in ep_name for f in filters["endpoint"]):
                continue

            filtered_methods = {}

            if show_methods:
                for method, details in endpoint.get("methods", {}).items():
                    method_upper = method.upper()

                    if filters.get("method") and method_upper not in [m.upper() for m in filters["method"]]:
                        continue

                    if filters.get("operationId"):
                        op_id = details.get("operationId", "")
                        if not any(f in op_id for f in filters["operationId"]):
                            continue

                    if filters.get("method_description"):
                        desc = details.get("method_description", "")
                        if not any(f in desc for f in filters["method_description"]):
                            continue

                    if filters.get("tags"):
                        method_tags = details.get("tags", [])
                        if not any(tag in method_tags for tag in filters["tags"]):
                            continue

                    if filters.get("parameters"):
                        param_names = [p.get("name") for p in details.get("parameters", [])]
                        if not any(p in param_names for p in filters["parameters"]):
                            continue

                    filtered_methods[method] = details

            if show_methods and not filtered_methods:
                continue

            filtered_endpoint = {
                "endpoint": ep_name,
            }

            if show_methods:
                filtered_endpoint["methods"] = filtered_methods

            if "parameters" in filters and endpoint.get("parameters"):
                filtered_endpoint["parameters"] = [
                    p for p in endpoint.get("parameters", [])
                    if not filters["parameters"] or p.get("name") in filters["parameters"]
                ]

            results.append(self.transform_endpoint(i, filtered_endpoint, filters))

        return "\n\n".join(results)


    def transform_endpoint(self, index, endpoint_data, filters):
        output = [f"**Endpoint **: `{endpoint_data.get('endpoint', 'Unknown')}`"]

        # Show only if explicitly included
        if "parameters" in filters:
            parameters = endpoint_data.get("parameters", [])
            if parameters:
                output.append("\n**Parameters**:")
                output.append(f"{parameters}")

        methods = endpoint_data.get("methods", {})
        if methods:
            for method, details in methods.items():
                output.append(f"\n**Request Type**: {method.upper()}")

                if "operationId" in filters and details.get('operationId'):
                    output.append(f"- **Operation ID**: `{details['operationId']}`")

                if "method_description" in filters and details.get('method_description'):
                    output.append(f"- **Description**: {details['method_description']}")

                if "parameters" in filters:
                    method_params = details.get("parameters", [])
                    output.append("\n  **Method Parameters:**")
                    if method_params:
                        output.append(f"{method_params}")
                    else:
                        output.append(" No parameters found.")

                if "tags" in filters:
                    tags = details.get("tags", [])
                    if tags:
                        output.append("\n  **Tags:**")
                        output.append(f"{tags}")

                if "responses" in filters:
                    responses = details.get("responses", [])
                    if responses:
                        output.append("\n  **Responses:**")
                        for response in responses:
                            if response.get("status_code"):
                                output.append(f"    - ***Status Code***: `{response['status_code']}`")
                            if response.get("response_description"):
                                output.append(f"      - **Description**: {response['response_description']}")
                            examples = response.get("content", {}).get("examples", {})
                            if examples:
                                output.append(f"      - ***Examples:***")
                                for content_type, example in examples.items():
                                    output.append(f"        - `{content_type}`: {json.dumps(example, indent=4)}")
                            schema = response.get("content", {}).get("schema", {})
                            if schema:
                                output.append(f"      - ***Schema***:")
                                if schema.get('title'):
                                    output.append(f"        - **Title**: {schema['title']}")
                                if schema.get('type'):
                                    output.append(f"        - **Type**: {schema['type']}")
                                properties = schema.get("properties", {})
                                if properties:
                                    output.append(f"        - **Properties:**")
                                    for prop, details in properties.items():
                                        if details.get('description'):
                                            output.append(
                                                f"          - `{prop}`: {details['description']} (Type: {details.get('type', 'Unknown')})\n")
        return "\n".join(output)

    def get_api_info(self):
        header = {key: value for key, value in self.openapi_spec.items() if key not in ["paths", "definitions"]}
        endpoints = [path["endpoint"] for path in self.openapi_spec["paths"]]

        # Ensure 'info' and 'description' keys exist
        info = header.setdefault("info", {})
        existing_description = info.get("description", "")
        info["description"] = f"{existing_description} There are {len(endpoints)} endpoints in this API.".strip()

        return json.dumps(header, indent=2)

    def get_host(self):
        schemes = self.openapi_spec.get('schemes', "")
        host = self.openapi_spec.get('host', '')
        return schemes[0] + "://" + host if schemes else host

    def get_all_endpoints(self):
        return [path['endpoint'] for path in self.openapi_spec['paths']]

    def get_methods_for_endpoint(self, endpoint):
        for path in self.openapi_spec['paths']:
            if path['endpoint'] == endpoint:
                return list(path['methods'].keys())
        return []

    def get_parameters_for_method(self, endpoint, method):
        for path in self.openapi_spec['paths']:
            if path['endpoint'] == endpoint:
                return path['methods'].get(method, {}).get('parameters', [])
        return []

    def get_methods_for_all_endpoints(self):
        return {path['endpoint']: list(path['methods'].keys()) for path in self.openapi_spec['paths']}

    def get_endpoint_details(self, endpoint):
        for path in self.openapi_spec['paths']:
            if path['endpoint'] == endpoint:
                return path
        return {}

    def get_endpoints_with_methods_and_descriptions(self):
        endpoints_info = {}
        for path in self.openapi_spec['paths']:
            endpoint = path['endpoint']
            methods_info = {
                method: details.get("method_description", "No description available")
                for method, details in path.get('methods', {}).items()
            }
            endpoints_info[endpoint] = methods_info
        return endpoints_info

    def get_all_operations(self):
        return {
            path['endpoint']: {
                method: {
                    "operationId": data.get("operationId", ""),
                    "description": data.get("method_description", "")
                }
                for method, data in path['methods'].items()
            }
            for path in self.openapi_spec['paths']
        }

    def get_parameters_for_endpoint(self, endpoint):
        for path in self.openapi_spec["paths"]:
            if path["endpoint"] == endpoint:
                parameters = []
                for method in path["methods"].values():
                    parameters.extend(method.get("parameters", []))
                return parameters
        return []