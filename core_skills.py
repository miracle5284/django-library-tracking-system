import random
rand_list = [random.randint(1, 20) for _ in range(10)]

list_comprehension_below_10 = [integers for integers in rand_list if integers < 10]

list_comprehension_below_10 = list(filter(lambda x: x < 10 , rand_list))
