async def _generate_opportunity_improvement(
        self, opportunity: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Generate improvement based on an opportunity, including actual code changes.

        Args:
            opportunity: Improvement opportunity

        Returns:
            Improvement dictionary with code changes or None
        """
        try:
            opp_type = opportunity.get("type", "")
            priority = opportunity.get("priority", 0)
            description = opportunity.get("description", "")
            suggested_action = opportunity.get("suggested_action", "")

            # Try to extract file path and function/class from opportunity
            file_path = None
            original_code = None
            refactored_code = None
            has_code_changes = False

            # Check if opportunity has affected functions with file paths
            affected_functions = opportunity.get("affected_functions", [])
            if affected_functions:
                # Use the first affected function to get file path
                func_info = affected_functions[0]
                module_path = func_info.get("module", "")
                function_name = func_info.get("function", "")

                if module_path:
                    # Try to read the file
                    full_path = self._resolve_file_path(module_path)
                    if full_path and full_path.exists():
                        try:
                            with open(full_path, 'r', encoding='utf-8') as f:
                                original_code = f.read()
                            file_path = str(full_path)
                            
                            # Generate refactored code using LLM
                            refactored_code = await self._generate_opportunity_refactor(
                                opp_type=opp_type,
                                description=description,
                                suggested_action=suggested_action,
                                function_name=function_name,
                                original_code=original_code,
                                priority=priority
                            )
                            
                            if refactored_code and refactored_code != original_code:
                                has_code_changes = True
                                logger.info(f"Successfully generated code changes for {function_name} in {file_path}")
                            else:
                                logger.warning(f"Failed to generate code changes for {function_name}, falling back to suggestion")
                        except Exception as e:
                            logger.error(f"Error reading or processing file {file_path}: {e}")

            # Determine category based on opportunity type
            if "performance" in opp_type.lower():
                category = "performance"
            elif "error" in opp_type.lower() or "exception" in opp_type.lower():
                category = "reliability"
            elif "test" in opp_type.lower():
                category = "testing"
            elif "complexity" in opp_type.lower():
                category = "complexity_reduction"
            else:
                category = "general"

            # Build improvement dictionary
            improvement = {
                "type": f"{category}_improvement" if category != "general" else "general_improvement",
                "description": description,
                "suggested_action": suggested_action,
                "priority": priority,
                "category": category,
            }

            # Add code-related fields if we have them
            if file_path:
                improvement["file_path"] = file_path
            if original_code:
                improvement["original_code"] = original_code
            if refactored_code:
                improvement["refactored_code"] = refactored_code
            improvement["has_code_changes"] = has_code_changes

            return improvement

        except Exception as e:
            logger.error(f"Error generating opportunity improvement: {e}")
            return None