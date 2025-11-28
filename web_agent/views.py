"""
Pydantic models for QA Agent
Copied from browser for structured output support
"""
from pydantic import BaseModel, ConfigDict, Field
from web_agent.tools.registry.views import ActionModel


class AgentOutput(BaseModel):
	"""LLM output structure - matches browser exactly"""
	model_config = ConfigDict(arbitrary_types_allowed=True, extra='forbid')

	thinking: str | None = None
	evaluation_previous_goal: str | None = None
	memory: str | None = None
	next_goal: str | None = None
	action: list[ActionModel] = Field(
		...,
		json_schema_extra={'min_items': 1},  # Ensure at least one action is provided
	)

	@classmethod
	def model_json_schema(cls, **kwargs):
		schema = super().model_json_schema(**kwargs)
		schema['required'] = ['evaluation_previous_goal', 'memory', 'next_goal', 'action']
		return schema

	@staticmethod
	def type_with_custom_actions(custom_actions: type[ActionModel]) -> type['AgentOutput']:
		"""Extend actions with custom actions - used to pass specific action types to LLM"""
		from pydantic import create_model

		model_ = create_model(
			'AgentOutput',
			__base__=AgentOutput,
			action=(
				list[custom_actions],  # type: ignore
				Field(..., description='List of actions to execute', json_schema_extra={'min_items': 1}),
			),
			__module__=AgentOutput.__module__,
		)
		return model_
