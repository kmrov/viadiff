# coding: utf8
import xml.etree.ElementTree as et


class ViaDiff:
    ID_FIELDS = ("Carrier", "FlightNumber", "Source", "Destination", )
    DATA_FIELDS = ("Class", "TicketType", )
    DATA_TIME_FIELDS = ("DepartureTimeStamp", "ArrivalTimeStamp", )
    ALL_FIELDS = ID_FIELDS + DATA_FIELDS + DATA_TIME_FIELDS

    def __init__(self, fid, data, prices, **kwargs):
        self.flights = []
        for idval, dataval in zip(fid, data):
            self.flights.append(
                {
                    k: v for k, v in zip(
                        self.ALL_FIELDS,
                        idval + dataval
                    )
                }
            )
        self.prices = prices

    @staticmethod
    def _parse_file(filename):
        # идентификатор полета, по которому они сравниваются
        def flight_id(flight):
            fid = tuple(
                flight.find(field).text
                for field in ViaDiff.ID_FIELDS
            )
            return fid

        # дополнительные данные (в т.ч. время без даты)
        def flight_data(flight):
            return tuple(
                flight.find(field).text
                for field in ViaDiff.DATA_FIELDS
            ) + tuple(
                flight.find(field).text.split("T")[1]
                for field in ViaDiff.DATA_TIME_FIELDS
            )

        def pricing(service_charges):
            return tuple(
                (service_charges.attrib["type"], service_charges.text)
            )

        def get_flights(element, selector):
            flight_ids = []
            flight_datas = []
            for el in element.findall(selector):
                flight_ids.append(flight_id(el))
                flight_datas.append(flight_data(el))
            return (tuple(flight_ids), tuple(flight_datas))

        flights = {}

        # Предположим, что документы всегда помещаются в память (иначе
        # нужно использовать iterparse, что немного сложнее).
        tree = et.parse(filename)

        return_present = False

        for flights_el in tree.findall("./PricedItineraries/Flights"):
            ids_onward, data_onward = get_flights(
                flights_el, "./OnwardPricedItinerary/Flights/Flight"
            )
            ids_return, data_return = get_flights(
                flights_el, "./ReturnPricedItinerary/Flights/Flight"
            )
            prices = (
                flights_el.find("Pricing").attrib["currency"],
                tuple(pricing(p) for p in flights_el.findall(
                    "./Pricing/ServiceCharges[@ChargeType='TotalAmount']"
                ))
            )

            if ids_return:
                flights[(ids_onward, ids_return)] = {
                    "prices": prices,
                    "data": (data_onward, data_return),
                }
                return_present = True
            else:
                flights[ids_onward] = {
                    "prices": prices,
                    "data": data_onward,
                }

        return (return_present, flights)

    @staticmethod
    def _compare_parsed(base_data, data):
        flights_added = [
            FlightsAdded(fid, **flight)
            for fid, flight in data.items()
            if fid not in base_data
        ]
        flights_removed = [
            FlightsRemoved(fid, **flight)
            for fid, flight in base_data.items()
            if fid not in data
        ]
        prices_changed = [
            PriceChanged(fid, old_prices=base_data[fid]["prices"], **flight)
            for fid, flight in data.items()
            if fid in base_data and
            flight["prices"] != base_data[fid]["prices"]
        ]
        data_changed = [
            DataChanged(fid, old_data=base_data[fid]["data"], **flight)
            for fid, flight in data.items()
            if fid in base_data and
            flight["data"] != base_data[fid]["data"]
        ]

        return (flights_added, flights_removed, prices_changed, data_changed)

    @staticmethod
    def compare_files(*filenames):
        files_data = [ViaDiff._parse_file(filename) for filename in filenames]

        base_return_present, base_data = files_data[0]
        if base_return_present:
            base_without_return = None
        diffs = {}
        for filename, (return_present, data) in zip(
                filenames[1:], files_data[1:]
        ):
            # Отдельно рассматриваем случаи, когда базовый файл по запросу
            # туда-обратно, а текущий - только туда, и наоборот. В таких
            # случаях сравниваем только данные "туда".
            if base_return_present and not return_present:
                if base_without_return is None:
                    base_without_return = {
                        k[0]: {
                            "prices": v["prices"],
                            "data": v["data"][0],
                        } for k, v in base_data.items()
                    }
                diffs[filename] = ViaDiff._compare_parsed(
                    base_without_return, data
                )
            elif return_present and not base_return_present:
                data_without_return = {
                    k[0]: {
                        "prices": v["prices"],
                        "data": v["data"][0],
                    } for k, v in data.items()
                }
                diffs[filename] = ViaDiff._compare_parsed(
                    base_data, data_without_return
                )
            else:
                diffs[filename] = ViaDiff._compare_parsed(base_data, data)
        return diffs


class FlightsAdded(ViaDiff):
    def __str__(self):
        return "Flights added: {}".format(self.flights)


class FlightsRemoved(ViaDiff):
    def __str__(self):
        return "Flights removed: {}".format(self.flights)


class PriceChanged(ViaDiff):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.old_prices = kwargs.get("old_prices", None)

    def __str__(self):
        return """Price changed for flights: {}
    was: {}
    now: {}""".format(
            self.flights, self.old_prices, self.prices
        )


class DataChanged(ViaDiff):
    def __init__(self, fid, old_data, *args, **kwargs):
        super().__init__(fid, *args, **kwargs)
        self.old_flights = []
        for idval, dataval in zip(fid, old_data):
            self.old_flights.append(
                {
                    k: v for k, v in zip(
                        self.ALL_FIELDS,
                        idval + dataval
                    )
                }
            )

    def __str__(self):
        return """Data changed for flights: {}
    was: {}""".format(
            self.flights, self.old_flights
        )
