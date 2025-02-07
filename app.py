from datetime import datetime, timedelta
from collections import defaultdict

class Person:
    def __init__(self, name, surname):
        self.name = name
        self.surname = surname
        self.payments = []
    
    def add_payment(self, amount, date):
        self.payments.append((amount, date))
    
    def total_paid(self):
        return sum(amount for amount, _ in self.payments)
    
    def __repr__(self):
        return f"{self.name} {self.surname}"

class Room:
    def __init__(self, name, area):
        self.name = name
        self.area = area
        self.occupants = []
    
    def add_occupant(self, person):
        self.occupants.append(person)

class PeriodError(ValueError):
    pass

class CostPeriod:
    def __init__(self, start_date: datetime, end_date: datetime, cost: float):
        if start_date >= end_date:
            raise ValueError("Start date must be before end date")
        self.start = start_date
        self.end = end_date
        self.cost = cost
    
    @property
    def duration_days(self):
        return (self.end - self.start).days + 1  # Inclusive
    
    def __repr__(self):
        return f"{self.start.strftime('%Y-%m-%d')} to {self.end.strftime('%Y-%m-%d')}: €{self.cost}"

class Utility:
    SHARING_TYPES = {'per_person', 'per_area', 'per_room'}
    
    def __init__(self, name: str, sharing_type: str):
        if sharing_type not in self.SHARING_TYPES:
            raise ValueError(f"Invalid sharing type. Use: {', '.join(self.SHARING_TYPES)}")
        
        self.name = name
        self.sharing_type = sharing_type
        self.periods = []
    
    def add_cost_period(self, period: CostPeriod):
        self._validate_new_period(period)
        self.periods.append(period)
        self.periods.sort(key=lambda p: p.start)
    
    def _validate_new_period(self, new_period: CostPeriod):
        for existing in self.periods:
            if (new_period.start <= existing.end and 
                new_period.end >= existing.start):
                raise PeriodError(f"Overlap with existing period {existing}")
        
        # Check for adjacent periods
        if not any(
            abs((new_period.start - p.end).days) == 1 or
            abs((p.start - new_period.end).days) == 1
            for p in self.periods
        ):
            if self.periods:  # Only check if not first period
                raise PeriodError("New period must be adjacent to existing periods")
    
    @property
    def total_cost(self):
        return sum(p.cost for p in self.periods)
    
    def __repr__(self):
        return f"{self.name} ({self.sharing_type}): {len(self.periods)} periods"

class Property:
    def __init__(self):
        self.rooms = []
        self.common_area = 0
        self.utilities = []
    
    def add_room(self, room):
        self.rooms.append(room)
    
    def set_common_area(self, area):
        self.common_area = area
    
    def add_utility(self, utility):
        self.utilities.append(utility)
    
    def _get_occupants(self):
        return [person for room in self.rooms for person in room.occupants]
    
    def calculate_shares(self, start_date: datetime, end_date: datetime):
        shares = defaultdict(float)
        total_days = (end_date - start_date).days + 1
        
        for utility in self.utilities:
            self._validate_utility_coverage(utility, start_date, end_date)
            
            for period in utility.periods:
                if period.end < start_date or period.start > end_date:
                    continue
                
                effective_start = max(period.start, start_date)
                effective_end = min(period.end, end_date)
                days_active = (effective_end - effective_start).days + 1
                cost_per_day = period.cost / period.duration_days
                
                # Calculate daily cost allocation
                daily_shares = self._calculate_daily_shares(
                    utility.sharing_type,
                    cost_per_day
                )
                
                # Apply pro-rata for active days
                for person, daily_share in daily_shares.items():
                    shares[person] += daily_share * days_active
    
        return shares
    
    def _calculate_daily_shares(self, sharing_type, daily_cost):
        shares = defaultdict(float)
        occupants = self._get_occupants()
        total_people = len(occupants)
        total_private_area = sum(r.area for r in self.rooms)
        total_area = total_private_area + self.common_area
        
        if sharing_type == 'per_person':
            if total_people == 0:
                raise ValueError("No occupants for per-person calculation")
            per_person = daily_cost / total_people
            for person in occupants:
                shares[person] = per_person
        
        elif sharing_type == 'per_area':
            if total_area == 0:
                raise ValueError("Zero area for per-area calculation")
            
            # Private areas
            for room in self.rooms:
                if room.occupants:
                    room_share = (room.area / total_area) * daily_cost
                    per_person = room_share / len(room.occupants)
                    for person in room.occupants:
                        shares[person] += per_person
            
            # Common area
            if self.common_area > 0:
                common_share = (self.common_area / total_area) * daily_cost
                per_person_common = common_share / total_people
                for person in occupants:
                    shares[person] += per_person_common
        
        elif sharing_type == 'per_room':
            occupied_rooms = [r for r in self.rooms if r.occupants]
            if not occupied_rooms:
                raise ValueError("No occupied rooms for per-room calculation")
            
            per_room = daily_cost / len(occupied_rooms)
            for room in occupied_rooms:
                per_person = per_room / len(room.occupants)
                for person in room.occupants:
                    shares[person] += per_person
        
        return shares
    
    def _validate_utility_coverage(self, utility, start_date, end_date):
        """Ensure the utility has continuous coverage for the period"""
        coverage_start = min(p.start for p in utility.periods)
        coverage_end = max(p.end for p in utility.periods)
        
        if coverage_start > start_date:
            raise PeriodError(f"{utility.name} starts after calculation period")
        if coverage_end < end_date:
            raise PeriodError(f"{utility.name} ends before calculation period")
        
        # Check adjacent periods
        sorted_periods = sorted(utility.periods, key=lambda p: p.start)
        for i in range(1, len(sorted_periods)):
            prev_end = sorted_periods[i-1].end
            curr_start = sorted_periods[i].start
            if (curr_start - prev_end).days != 1:
                raise PeriodError(
                    f"Gap in {utility.name} between {prev_end} and {curr_start}"
                )


# Example usage
if __name__ == "__main__":
    # Setup property
    house = Property()
    house.set_common_area(40)
    
    # Create rooms and occupants
    room1 = Room('wohnzimmer', 40)
    room2 = Room('schlafzimmer', 20)
    alice = Person("Alice", "Smith")
    bob = Person("Bob", "Jones")
    room1.add_occupant(alice)
    room2.add_occupant(bob)
    house.add_room(room1)
    house.add_room(room2)
    
    # Create utility with multiple cost periods
    electricity = Utility("Electricity", "per_area")
    electricity.add_cost_period(CostPeriod(
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 8, 31),
        cost=500.00
    ))
    electricity.add_cost_period(CostPeriod(
        start_date=datetime(2024, 9, 1),
        end_date=datetime(2024, 12, 31),
        cost=100.00
    ))
    house.add_utility(electricity)
    
    # Calculate shares for the full year
    shares = house.calculate_shares(
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 11, 30)
    )
    
    print("Annual Utility Shares:")
    for person, amount in shares.items():
        print(f"{person}: €{amount:.2f}")