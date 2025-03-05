import random
from abc import ABC, abstractmethod
from typing import Callable, Dict, List, Optional

from llego.operators.individual import Individual
from llego.operators.offspring_selector import OffspringSelector
from llego.operators.parent_sampler import ParentSampler
from llego.utils.llm_api import LLM_API


class EvolutionaryOperator(ABC):
    def __init__(
        self,
        llm_api: LLM_API,
        prompt_prefix: str,
        ### evolutionary operator hyperparameters
        num_offspring: int,  # number of offspring generated by each genetic operation
        num_parents: int,  # number of parents selected for each genetic operation
        ordering: str,  # ordering of parents involved in each genetic operation
        parent_sampling_strategy: str,  # function for selecting parents for genetic operation
        parent_sampling_kwargs: Dict,  # kwargs for parent sampling strategy
        llm_output_parser: Callable,  # function for parsing output of LLM
        lower_is_better: bool = False,  # flag for whether lower fitness is better
        seed: int = 0,  # seed for random number generation
    ) -> None:

        self.llm_api = llm_api
        self.prompt_prefix = prompt_prefix
        self.num_offspring = num_offspring
        self.num_parents = num_parents
        self.ordering = ordering
        self.parent_sampling_strategy = parent_sampling_strategy
        self.parent_sampling_kwargs = parent_sampling_kwargs
        self.llm_output_parser = llm_output_parser
        self.seed = seed

        assert isinstance(
            lower_is_better, bool
        ), "lower_is_better should be of type boolean"

        self.lower_is_better = lower_is_better

        self.parent_sampler = ParentSampler(
            sampling_strategy=parent_sampling_strategy,
            num_parents=num_parents,
            lower_is_better=lower_is_better,
            seed=seed,
            **parent_sampling_kwargs,
        )

    def _check_population(self, population: List[Individual]) -> None:
        """
        Check if population is valid
        """
        assert isinstance(population, list), f"Expected list but got {type(population)}"
        for individual in population:
            assert isinstance(
                individual, Individual
            ), f"Expected Individual but got {type(individual)}"
            assert (
                individual.llm_readable_format is not None
            ), f"Individual {individual} does not have llm_readable_format"
            assert (
                individual.machine_readable_format is not None
            ), f"Individual {individual} does not have machine_readable_format"
            assert (
                individual.fitness is not None
            ), f"Individual {individual} does not have fitness"
            assert (
                individual.functional_signature is not None
            ), f"Individual {individual} does not have functional_signature"

    def _serialize_parents(
        self,
        parents: List[Individual],
        with_fitness: bool,
        float_precision: Optional[int] = None,
        sorting_key: Optional[str] = None,
    ) -> List[Dict]:
        """
        Serialize parents for sending to LLM
        """

        def max_decimal_places(float_list):
            """Get maximum decimal places in a list of floats"""
            return max(
                len(str(f).rstrip("0").split(".")[-1])
                for f in float_list
                if "." in str(f)
            )

        assert isinstance(parents, list), f"Expected list but got {type(parents)}"
        assert all(
            [isinstance(parent, Individual) for parent in parents]
        ), f"Expected list of Individuals but got {type(parents[0])}"

        if with_fitness:
            n_dp = max_decimal_places([parent.fitness for parent in parents])
            n_dp = max(n_dp, 4)
            precision = float_precision if float_precision is not None else n_dp
            parents = self._reorder_parents(parents, sorting_key=sorting_key)
            serialized_parents = []
            for parent in parents:
                parent_dict = {"Q": f"## {parent.llm_readable_format} ##"}
                for key, value in parent.fitness.items():
                    parent_dict[key] = f"{value:.{precision}f}"
                serialized_parents.append(parent_dict)

        else:
            parents = self._reorder_parents(parents)
            serialized_parents = [
                {"Q": f"## {parent.llm_readable_format} ##"} for parent in parents
            ]

        assert len(serialized_parents) == len(
            parents
        ), f"Expected {len(parents)} serialized parents but got {len(serialized_parents)}"
        return serialized_parents

    def _reorder_parents(
        self, parents: List[Individual], sorting_key: Optional[str] = None
    ) -> List[Individual]:
        """
        Reorder parents based on ordering
        """
        if self.ordering == "random":
            random.shuffle(parents)
        elif self.ordering == "decreasing":
            assert sorting_key is not None, "sorting_key should not be None"
            if self.lower_is_better:
                parents = sorted(
                    parents,
                    key=lambda x: x.fitness[sorting_key],  # type: ignore
                    reverse=False,
                )
            else:
                parents = sorted(
                    parents,
                    key=lambda x: x.fitness[sorting_key],  # type: ignore
                    reverse=True,
                )
        elif self.ordering == "increasing":
            if self.lower_is_better:
                parents = sorted(
                    parents,
                    key=lambda x: x.fitness[sorting_key],  # type: ignore
                    reverse=True,
                )
            else:
                parents = sorted(
                    parents,
                    key=lambda x: x.fitness[sorting_key],  # type: ignore
                    reverse=False,
                )
        else:
            raise ValueError(f"Invalid ordering {self.ordering}")

        return parents

    @abstractmethod
    def _create_prompt_for_one_operation(self, parents: List[Individual]) -> str:
        raise NotImplementedError

    @abstractmethod
    def generate_offspring(self, population, total_num_offspring, **kwargs) -> List:
        raise NotImplementedError
