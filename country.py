class Country:
    def __init__(self, name, capital, flag_image, territories,
                 military_strength, economic_power, population, stability,
                 personality_type, decision_frequency, volatility, nuclear):

        # Identity — constant
        self.name = name
        self.capital = capital
        self.flag_image = flag_image
        self.territories = territories

        # Stats — change slowly
        self.military_strength = military_strength
        self.economic_power = economic_power
        self.population = population
        self.stability = stability

        # Personality — constant
        self.personality_type = personality_type
        self.decision_frequency = decision_frequency
        self.volatility = volatility

        # Relationships — built later
        self.relationships = {}

        # Cooldown — starts ready
        self.action_cooldown = 0

        self.nuclear = nuclear  # bool — affects invasion likelihood